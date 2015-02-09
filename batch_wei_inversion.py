#!/usr/bin/python
import commands,os,sys
import pickle
import pbs_util
from pbs_util import WeiInversionBookkeeper
import sepbase
import batch_mig_script_nompi as batch_mig
import batch_wet_script_nompi as batch_wet
import calc_wemva_objfunc as wemva_obj

## This program glues all the batch processed wave-equation operators to make an inversion loop.

# Usage: *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perjob=10 path=path_out prefix=waz3d queues=q35,default nnodes=0 njobmax=5 ish_beg=0 vel=vel.H niter=10 iiter=0 path_iter=path_to_save_results_per_iteration load_save=load_fn,save_fn
# load_save is the bookkeeping object after seralization, this is used for resuming computation.


def FitParabola(x_coefs, func_vals):
  '''Given 3 points of (x,y), return the fitted parabola coefs [a,b,c] (ax^2+bx+c).'''
  x1,x2,x3 = x_coefs
  y1,y2,y3 = func_vals
  denom = (x1-x2)*(x1-x3)*(x2-x3)
  xmax_abs = max([abs(x) for x in x_coefs])
  assert abs(denom) > xmax_abs*xmax_abs*xmax_abs*1e-6  # Sanity check to avoid divide-by-zero.
  coef = [0]*3
  coef[0] = (x3*(y2-y1) + x2*(y1-y3) + x1*(y3-y2)) / denom;
  coef[1] = (x3*x3*(y1-y2) + x2*x2*(y3-y1) + x1*x1*(y2-y3)) / denom;
  coef[2] = (x2*x3*(x2-x3)*y1 + x3*x1*(x3-x1)*y2 + x1*x2*(x1-x2)*y3)/denom;
  return coef

def ComputeOptimalStepSize(alpha1,alpha2,costfunc0,costfunc1,costfunc2):
  '''Given the objectfunction values at 3 trail pts, with 0,alpha1,alpha2 as the stepsize,
  return the optimal stepsize that minimize the cost functions).'''
  stepsizes = [0.,alpha1,alpha2]; costfuncs = [costfunc0,costfunc1,costfunc2]
  a,b,c = FitParabola(stepsizes, costfuncs)
  opt_stepsize = 0.
  # print stepsizes, costfuncs
  if a <= 0:  # Pathlogical case, the parabola is curving downward, pick the optimal solution among the 3 given sizes.
    print "The parabola is curving downward!"
    min_index = costfuncs.index(min(costfuncs))
    if min_index == 0:
      print "min_index=0, stepping halted! Should reduce the stepsize by 4."
      opt_stepsize = stepsizes[1]*0.25  # Pure heuristic, reduce the stepsize.
    elif min_index == 1:
      opt_stepsize = stepsizes[1]
      assert False  # Impossible case, since curving downward
    else:  # min_index == 2
      opt_stepsize = 2.0*stepsizes[2]  # Try making a bigger step.
  else:  # Normal case, curving upwards.
    opt_stepsize = -b/(2*a)
    if opt_stepsize > 2*alpha2:  # Hold the rein a bit.
      opt_stepsize = 2*alpha2
    elif opt_stepsize <= 0:
      print "opt_stepsize<0, stepping halted! Reduce the stepsize by 4."
      opt_stepsize = stepsizes[1]*0.25 # Pure heuristic, reduce the stepsize.
    else:
      pass
  return opt_stepsize

def GenCmdlineArgsFromDict(eq_args):
  '''Return a long string that contains all key=val pairs in eq_args.'''
  return ["%s=%s" % (key,eq_args[key]) for key in eq_args]

if __name__ == '__main__':
  eq_args_cmdline,args = sepbase.parse_args(sys.argv[1:])
  assert args == []
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_cmdline)
  param_reader = pbs_util.ParallelParamReader(dict_args)
  path_tmp = param_reader.path_tmp
  solver_par = pbs_util.SolverParamReader(dict_args)
  prefix = dict_args['prefix']
  path_iter = os.path.abspath(dict_args['path_iter'])  # The path that save the intermediate results
  niter = int(dict_args['niter'])
  iter_beg = int(dict_args.get('iter_beg',0))
  str_ws_wnd_wet = dict_args.get('ws_wnd_wet')  # Might use different frequency sampling for tomo operator.
  str_ws_wnd = dict_args.get('ws_wnd')
  # The inversion code, v is vel model, s is search direction.
  fn_v0 = dict_args['vel']; # v is the current iteration vel model.
  fn_srch = ""; fn_srch_prev = ""
  # Initiate alpha and smoothing scale.
  alpha_init = solver_par.initial_perturb_scale
  smooth_rects_init = solver_par.smooth_rect_sizes[:]
  # For bookkeeping, load/save from a previous executing point.
  fn_load,fn_save= dict_args['load_save'].split(',')
  resume_from_saving_pt = False
  if os.path.exists(fn_load):  # See if we can resume from a saved point before
    f = open(fn_load,'rb'); wei_inv_bookkeeper = pickle.load(f); f.close()
    print "Loading the inversion bookkeeper...: %s" % wei_inv_bookkeeper
    assert (isinstance(wei_inv_bookkeeper,WeiInversionBookkeeper))
    # Restore the values of those variables 
    # e.g: objfuncs, stepsizes(alphas), alpha, etc
    iter_beg = wei_inv_bookkeeper.iter
    resume_from_saving_pt = True
  else:  # No file to load, then create wei_inv_bookkeeper on my own
    wei_inv_bookkeeper = WeiInversionBookkeeper([],[])
    wei_inv_bookkeeper.alpha = alpha_init  # This case, we will use alpha designated by the cmdline.
    # See if we can pick up from somewhere we recorded previously, by
    # checking if the inverted velocity file from last time is recorded.
    iter_beg_old = iter_beg
    for iter in range(niter-1, iter_beg_old-1, -1):  # From [niter-1 to iter_beg], see if we have fn_vn name in place.
      fn_prefix = "%s/iter%02d" % (path_iter,iter)
      fn_vn = "%s-velnew.H" % fn_prefix
      if pbs_util.CheckSephFileError(fn_vn,False)==0:
        iter_beg = iter+1  # Starting from this new iteration number.
        wei_inv_bookkeeper.iter = iter_beg
        wei_inv_bookkeeper.fn_v = fn_vn  # Set the existing fn_vn as the starting velocity model.
        # Further extra extra info like stepsizes(alpha) from the history file.
        str_alphas = sepbase.get_sep_his_par(fn_vn,"stepsizes")
        if str_alphas:  # We can start from iter+1 instead of the very begining.
          wei_inv_bookkeeper.stepsizes = map(float,str_alphas.split(','))
        str_objfuncs = sepbase.get_sep_his_par(fn_vn,"objfuncs")
        if str_objfuncs:
          wei_inv_bookkeeper.objfuncs = map(float,str_objfuncs.split(','))
        break
  wib = wei_inv_bookkeeper  # An acronym, less typing.
  if wib.fn_v is None: wib.fn_v = fn_v0
  if wib.alpha is None: wib.alpha = alpha_init
  if not wib.smooth_rects: wib.smooth_rects = smooth_rects_init
  print "Current inversion bookkeeper status: %s" % wib
  # The main inversion loop.
  for wib.iter in range(iter_beg, niter):
    in_loading_stage = (wib.iter==iter_beg and resume_from_saving_pt)
    # Calc I(v_k) and J_k, and gradient g_k (i.e. fn_dv)
    fn_prefix = "%s/iter%02d" % (path_iter,wib.iter)
    fn_img = "%s-img.H" % fn_prefix
    eq_args_cmdline['vel'] = wib.fn_v
    eq_args_cmdline['img'] = fn_img
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.IMG_CALC:
      assert wib.fn_prefix == fn_prefix
      assert pbs_util.CheckSephFileError(fn_img) == 0
    else:  # Record status and make a save
      wib.smooth_rects_history.append(wib.smooth_rects[:])
      wib.fn_prefix = fn_prefix
      batch_mig.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      wib.Save(WeiInversionBookkeeper.IMG_CALC,fn_save)
    fn_dimg = "%s-dimg.H" % fn_prefix
    fn_bimgh0 = "%s-bimgh0.H" % fn_prefix; fn_imgh0zxy = "%s-imgh0zxy.H" % fn_prefix  # Optionally need this in RMO obj func.
    eq_args_cmdline["dimg"] = fn_dimg
    eq_args_cmdline["bimgh0"] = fn_bimgh0
    eq_args_cmdline["imgh0zxy"] = fn_imgh0zxy
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.DIMG_CALC:
      assert pbs_util.CheckSephFileError(fn_dimg) == 0
      assert wib.objfunc != None
    else:
      wib.objfunc = wemva_obj.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      wib.Save(WeiInversionBookkeeper.DIMG_CALC,fn_save)
    # Compute gradient dvel from dimg using WET operator.
    fn_dv = "%s-dvel.H" % fn_prefix
    eq_args_cmdline["dvel"] = fn_dv
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.GRAD_CALC:
      assert pbs_util.CheckSephFileError(fn_dv) == 0
    else:
      # Change the frequency sampling scheme
      if str_ws_wnd_wet:
        eq_args_cmdline['ws_wnd'] = str_ws_wnd_wet
      batch_wet.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      # Restore frequency sampling scheme
      if str_ws_wnd_wet:
        if str_ws_wnd: eq_args_cmdline['ws_wnd'] = str_ws_wnd
        else: del eq_args_cmdline['ws_wnd']
      # Compute search direction s_k from g_k [and s_{i-1}], and apply preconditioning (amplitude scaling and smoothing).
      wib.Save(WeiInversionBookkeeper.GRAD_CALC,fn_save)
    fn_srch = "%s-srch.H" % fn_prefix
    fn_srch_prev = ""  # Currently just use steepest descent.
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.SRCH_CALC:
      assert pbs_util.CheckSephFileError(fn_srch,False)==0
    else:
      cmd = ('%s/GenSrchDirFromGradient.x <%s srch_prev=%s >%s rect1=%d rect2=%d rect3=%d datapath=%s/' %
             (dict_args['YANG_BIN'], fn_dv, fn_srch_prev, fn_srch, 
              wib.smooth_rects[0],wib.smooth_rects[1],wib.smooth_rects[2], path_iter))
      sepbase.RunShellCmd(cmd,True)
      # Make sure the expected output file is generated.
      assert pbs_util.CheckSephFileError(fn_srch,True)==0
      # Adjust the smooth scale after each iteration
      for i in range(len(wib.smooth_rects)):
        wib.smooth_rects[i] -= solver_par.smooth_rect_reductions[i]
        if wib.smooth_rects[i]<1: wib.smooth_rects[i]=1
      wib.Save(WeiInversionBookkeeper.SRCH_CALC,fn_save)
    # Compute step size by trying out two trial model points along the s_k dir,
    # stepsizes are alpha1,alpha2
    fn_v1 = "%s-vel1.H" % fn_prefix; fn_v2 = "%s-vel2.H" % fn_prefix
    alpha1 = wib.alpha; alpha2 = 2*alpha1
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.VEL12_CALC:
      assert pbs_util.CheckSephFileError(fn_v1,False)==0
      assert pbs_util.CheckSephFileError(fn_v2,False)==0
    else:
      cmd = ('%s/GenTrialModelFromSrchDir.x <%s srch=%s stepsize=%f,%f vmax=%g vmin=%g output=%s,%s datapath=%s/ ' % 
           (dict_args['YANG_BIN'], wib.fn_v,fn_srch,alpha1,alpha2,solver_par.maxval,solver_par.minval, fn_v1,fn_v2, path_iter))
      sepbase.RunShellCmd(cmd,True)
      assert pbs_util.CheckSephFileError(fn_v1,False)==0
      assert pbs_util.CheckSephFileError(fn_v2,False)==0
      wib.Save(WeiInversionBookkeeper.VEL12_CALC,fn_save)

    # After fn_v1 and fn_v2 are in place, perform migration.
    fn_img1 = "%s-img1.H" % fn_prefix; fn_img2 = "%s-img2.H" % fn_prefix
    del eq_args_cmdline["dimg"]
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.IMG1_CALC:
      assert pbs_util.CheckSephFileError(fn_img1,False)==0
    else:
      eq_args_cmdline["vel"] = fn_v1; eq_args_cmdline["img"] = fn_img1
      batch_mig.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      wib.Save(WeiInversionBookkeeper.IMG1_CALC,fn_save)
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.OBJ1_CALC:
      assert wib.objfunc1 != None
    else:
      wib.objfunc1 = wemva_obj.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      wib.Save(WeiInversionBookkeeper.OBJ1_CALC,fn_save)
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.IMG2_CALC:
      assert pbs_util.CheckSephFileError(fn_img2,False)==0
    else:
      eq_args_cmdline["vel"] = fn_v2; eq_args_cmdline["img"] = fn_img2
      batch_mig.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      wib.Save(WeiInversionBookkeeper.IMG2_CALC,fn_save)
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.OBJ2_CALC:
      assert wib.objfunc2 != None
    else:
      wib.objfunc2 = wemva_obj.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
      wib.Save(WeiInversionBookkeeper.OBJ2_CALC,fn_save)

    fn_vn = "%s-velnew.H" % fn_prefix
    if in_loading_stage and wib.resume_stage >= WeiInversionBookkeeper.VELNEW_CALC:
      assert pbs_util.CheckSephFileError(fn_vn,True)==0
    else:
      # Compute step-length alpha based on objfunc[,1,2]
      wib.alpha = ComputeOptimalStepSize(alpha1,alpha2,wib.objfunc,wib.objfunc1,wib.objfunc2)
      objfuncs3 = [wib.objfunc, wib.objfunc1, wib.objfunc2]
      wib.objfuncs.extend(objfuncs3)
      print "objfuncs for current iter: ", objfuncs3, [alpha1,alpha2,wib.alpha]
      wib.stepsizes.append(wib.alpha);
      # Compute the updated vel model, the filename is written to fn_v
      cmd = ('%s/GenTrialModelFromSrchDir.x <%s srch=%s stepsize=%f vmax=%g vmin=%g output=%s datapath=%s/' %
             (dict_args['YANG_BIN'], wib.fn_v,fn_srch,wib.alpha, solver_par.maxval,solver_par.minval, fn_vn, path_iter))
      sepbase.RunShellCmd(cmd, True);
      assert pbs_util.CheckSephFileError(fn_vn,True)==0
      # Write the alpha and objfuncs history to fn_vn
      fp = open(fn_vn,'a');
      fp.write("\nstepsizes=%s\n" % ','.join(["%g"%x for x in wib.stepsizes]))
      fp.write("objfuncs=%s\n" % ','.join(["%g"%x for x in wib.objfuncs]))
      fp.close()
      wib.Save(WeiInversionBookkeeper.VELNEW_CALC,fn_save)
    # Update v_{k+1} := v_k.
    wib.fn_v = fn_vn
    fn_srch_prev = fn_srch
  # end iteration
  print "!Finished. The final inverted model is saved at: %s" % os.path.abspath(wib.fn_v)
  print 'objfuncs=','\t'.join(["%g" % val for val in wib.objfuncs])
  print 'stepsizes=','\t'.join(["%g" % val for val in wib.stepsizes])


