#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase
import batch_mig_script_nompi as batch_mig
import batch_wet_script_nompi as batch_wet
import calc_wemva_objfunc as wemva_obj

## This program glues all the batch processed wave-equation operators to make an inversion loop.

# Usage: *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perjob=10 path=path_out prefix=waz3d queues=q35,default nnodes=0 njobmax=5 ish_beg=0 vel=vel.H niter=10 iiter=0 path_iter=path_to_save_results_per_iteration

def ComputeOptimalStepSize(alpha1,alpha2,costfunc0,costfunc1,costfunc2):
  '''Given the objectfunction values at 3 trail pts, with 0,alpha1,alpha2 as the stepsize,
  return the optimal stepsize that minimize the cost functions).'''
  stepsizes = [0.,alpha1,alpha2]; costfuncs = [costfunc0,costfunc1,costfunc2]
  a,b,c = FitParabola(stepsizes, costfuncs)
  opt_stepsize = 0.
  print stepsizes, costfuncs
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

  # The inversion code, v is vel model, s is search direction.
  fn_v0 = dict_args['vel']; fn_v = fn_v0  # v is the current iteration vel model.
  fn_srch = ""; fn_srch_prev = ""
  objfuncs = []; objfunc = 0.0; alphas = []; alpha = 0.0
  # Initiate alpha
  alpha = solver_par.initial_perturb_scale
  smooth_rects = solver_par.smooth_rect_sizes[:]
  # See if we can pick up from somewhere we recorded previously.
  iter_beg_old = iter_beg
  for iter in range(niter-1, iter_beg_old-1, -1):  # From [niter-1 to iter_beg], see if we have fn_vn name in place.
    fn_prefix = "%s/iter%02d" % (path_iter,iter)
    fn_vn = "%s-velnew.H" % fn_prefix
    if pbs_util.CheckSephFileError(fn_v1,False)==0:
      # Further extra stepsize info (alpha)
      str_alphas = get_sep_his_par("alphas")
      if str_alphas:  # We can start from iter+1 instead of the very begining.
        alpha = str_alphas.split(',')[-1]
        iter_beg = iter+1
      break
  # The main inversion loop.
  for iter in range(iter_beg, niter):
    # Calc I(v_k) and J_k, and gradient g_k (i.e. fn_dv)
    fn_prefix = "%s/iter%02d" % (path_iter,iter)
    fn_img = "%s-img.H" % fn_prefix
    eq_args_cmdline['vel'] = fn_v
    eq_args_cmdline['img'] = fn_img
    batch_mig.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    fn_dimg = "%s-dimg.H" % fn_prefix
    eq_args_cmdline["dimg"] = fn_dimg
    objfunc = wemva_obj.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    # Compute gradient dvel from dimg using WET operator.
    fn_dv = "%s-dvel.H" % fn_prefix
    eq_args_cmdline["dvel"] = fn_dv
    batch_wet.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    # Compute search direction s_k from g_k [and s_{i-1}], and apply preconditioning (amplitude scaling and smoothing).
    fn_srch = "%s-srch.H" % fn_prefix
    fn_srch_prev = ""  # Currently just use steepest descent.
    if pbs_util.CheckSephFileError(fn_srch,True) != 0:
      cmd = ('%s/GenSrchDirFromGradient.x <%s srch_prev=%s >%s rect1=%d rect2=%d rect3=%d' %
             (dict_args['YANG_BIN'], fn_dv, fn_srch_prev, fn_srch, 
              smooth_rects[0],smooth_rects[1],smooth_rects[2]))
      sepbase.RunShellCmd(cmd,True)
      # Make sure the expected output file is generated.
      assert pbs_util.CheckSephFileError(fn_srch,True)==0
    # Adjust the smooth scale after each iteration
    for i in range(len(smooth_rects)):
      smooth_rects[i] -= solver_par.smooth_rect_sizes[i]
      if smooth_rects[i]<1: smooth_rects[i]=1
    # Compute step size by trying out two trial model points along the s_k dir,
    # stepsizes are alpha1,alpha2
    fn_v1 = "%s-vel1.H" % fn_prefix; fn_v2 = "%s-vel2.H" % fn_prefix
    alpha1 = alpha; alpha2 = 2*alpha1
    cmd = ('%s/GenTrialModelFromSrchDir.x <%s srch=%s stepsize=%f,%f vmax=%g vmin=%g output=%s,%s' % 
           (dict_args['YANG_BIN'], fn_v,fn_srch,alpha1,alpha2,solver_par.maxval,solver_par.minval, fn_v1,fn_v2))
    sepbase.RunShellCmd(cmd,True)
    assert pbs_util.CheckSephFileError(fn_v1,False)==0
    assert pbs_util.CheckSephFileError(fn_v2,False)==0
    # After fn_v1 and fn_v2 are in place, perform migration.
    fn_img1 = "%s-img1.H" % fn_prefix; fn_img2 = "%s-img2.H" % fn_prefix
    del eq_args_cmdline["dimg"]
    eq_args_cmdline["vel"] = fn_v1; eq_args_cmdline["img"] = fn_img1
    batch_mig.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    objfunc1 = wemva_obj.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    eq_args_cmdline["vel"] = fn_v2; eq_args_cmdline["img"] = fn_img2
    batch_mig.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    objfunc2 = wemva_obj.Run(GenCmdlineArgsFromDict(eq_args_cmdline))
    # Compute step-length alpha based on objfunc[,1,2]
    alpha = ComputeOptimalStepSize(alpha1,alpha2,objfunc,objfunc1,objfunc2)
    objfuncs.extend([objfunc, objfunc1, objfunc2])
    print "objfuncs for current iter: ", [objfunc, objfunc1, objfunc2], [alpha1,alpha2,alpha]
    alphas.append(alpha);
    # Compute the updated vel model, the filename is written to fn_v
    fn_vn = "%s-velnew.H" % fn_prefix
    cmd = ('%s/GenTrialModelFromSrchDir.x <%s srch=%s stepsize=%f vmax=%g vmin=%g output=%s' %
           (dict_args['YANG_BIN'], fn_v,fn_srch,alpha, solver_par.maxval,solver_par.minval, fn_vn))
    sepbase.RunShellCmd(cmd, True);
    assert pbs_util.CheckSephFileError(fn_vn,False)==0
    # Write the alpha and objfuncs history to fn_vn
    fp = open(fn_vn,'a');
    fp.write("alphas=%s\n" % ','.join(["%g"%x for x in alphas]))
    fp.write("objfuncs=%s\n" % ','.join(["%g"%x for x in objfuncs]))
    fp.close()
    # Update v_{k+1} := v_k.
    fn_v = fn_vn
    fn_srch_prev = fn_srch
  # end iteration
  print "!Finished. The final inverted model is saved at: %s" % os.path.abspath(fn_v)
  print 'objfuncs=','\t'.join(["%g" % val for val in objfuncs])
  print 'stepsizes=','\t'.join(["%g" % val for val in alphas])

