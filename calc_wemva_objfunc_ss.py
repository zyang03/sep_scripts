#!/usr/bin/python
import commands,os,sys
import pbs_util
from pbs_util import CheckPrevCmdResultCShellScript
import re
import sepbase

## This program will compute the wemva objective function given an input image, it also computes the delta image (optional, if dimg= parameter is supplied. If calc_ang_gather=y, then will calc angle gather.
## It will submit jobs to pbs scheduling system.
# Usage: *.py param=wemva_obj.param pbs_template=pbs_script_tmpl.sh path_out=path_out queues=q35 njobmax=5 \
#             img=img.H b3D=n wemva_type=  [dimg=dimg.H] \
#             [calc_ang_gather=n]

# The underlying binary calling format:
# CalcWemvaObjFunc.x img=image.H [dimg=dimg.H] b3D=n wemva_type=61 

# If calculate angle gather, then 
# (hx,hy,x,y,z)->transp->(x,y,z,hx,hy)->YFt3d->
# (kx,ky,kz,hx,hy)->transp->(hx,hy,kx,ky,kz)->Off2Ang3d_kxyz.x->
# (gamma, azim, kx,ky,kz) -> transp ->(kx,ky,kz,gamma,azim) -> YFt3d->
# (x,y,z,gamma,azim) -> transp -> (z,gamma,azim,x,y) -> RMO ->
# (z,gamma,azim,x,y) -> Transp -> (x,y,z,gamma,azim) -> Ft3d ->
# (kx,ky,kz,gamma,azim) -> Transp -> (gamma,azim,kx,ky,kz) -> Off2Ang3d_kxyz.x ->
# (hx,hy,kx,ky,kz) -> Transp -> (kx,ky,kz,hx,ky) -> YFt3d ->
# (x,y,z,hx,hy) -> Transp -> (hx,hy,x,y,z)
# That is 9 Transps, 4 YFt3d and 1 Off2Ang_kxyz Mapping

def Run(argv):
  '''Return the value of objective function calcualted.'''
  print "Run script with params:", argv
  eq_args_from_cmdline,args = sepbase.parse_args(argv)
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.JobParamReader(dict_args)
  prefix = param_reader.prefix
  path_out = param_reader.path_out
  path_tmp = param_reader.path_tmp
  # Get the input image file.
  fn_img = os.path.abspath(dict_args['img'])
  fn_img_path, fn_img_basename = os.path.split(fn_img)
  # string fn_img_base_wo_ext serves as a single unique identifier.
  fn_img_base_wo_ext = os.path.splitext(fn_img_basename)[0]
  # check if need to compute image perturbation.
  calc_dimg = False
  fn_dimg = dict_args.get('dimg')
  if fn_dimg is not None:
    calc_dimg = True
    fn_dimg = os.path.abspath(fn_dimg)
  b3D = dict_args['b3D']
  wemva_type = dict_args['wemva_type']
  # Initialize script_creators and PbsSubmitter.
  pbs_script_creator = pbs_util.PbsScriptCreator(param_reader)
  assert param_reader.queues[0] != 'default'  # Put sep queue ahead of the default queue.
  pbs_submitter = pbs_util.PbsSubmitter(zip(param_reader.queues, param_reader.queues_cap), param_reader.total_jobs_cap, dict_args['user'])
  obj_func_value = None
  # Check input file validity.
  file_error = pbs_util.CheckSephFileError(fn_img,False)
  assert file_error == 0, "The input file: %s is incorrect: %d" % (fn_img, file_error)
  ax_x = sepbase.get_sep_axis_params(fn_img,3)
  ax_y = sepbase.get_sep_axis_params(fn_img,4)
  ax_z = sepbase.get_sep_axis_params(fn_img,5)
  nhx = int(sepbase.get_sep_axis_params(fn_img,1)[0])
  nhy = int(sepbase.get_sep_axis_params(fn_img,2)[0])
  ss_ratio = 2
  n1_ss = (int(ax_x[0])-1)/ss_ratio+1;
  ax_x_ss = ax_x[:]; ax_x_ss[0]=str(n1_ss); ax_x_ss[2]=str(float(ax_x[2])*ss_ratio)
  n2_ss = (int(ax_y[0])-1)/ss_ratio+1;
  ax_y_ss = ax_y[:]; ax_y_ss[0]=str(n1_ss); ax_y_ss[2]=str(float(ax_y[2])*ss_ratio)
  n3_ss = int(ax_z[0])
  # Check if need to compute angle gather
  b = dict_args.get('calc_ang_gather')
  calc_ang_gather = (b=='y' or b=='1')
  if calc_ang_gather:  # Need to compute angle gather first.
    fn_imgh0_zxy = os.path.abspath(dict_args['imgh0zxy'])
    fn_img_ang = "%s/%s-ang.H" % (fn_img_path, fn_img_base_wo_ext)
    fnt_imgh_subsample = "%s/%s-ss2.H" % (fn_img_path, fn_img_base_wo_ext)
    fn_dimg_ang = "%s/%s-dimg-ang.H" % (fn_img_path, fn_img_base_wo_ext)
    while True:
      job_identifier = 'ang-'+fn_img_base_wo_ext
      pbs_submitter.WaitOnAllJobsFinish(job_identifier)
      pbs_script_creator.CreateScriptForNewJob(job_identifier)
      file_error = pbs_util.CheckSephFileError(fn_img_ang,False)
      if file_error == 0:
        print "The image gather file is good, skip: %s " % fn_img_ang
        break
      else:  # Compute the angle gather
        scripts = []  # Subsample the x,y first
        cmd = "time Window3d <%s j3=2 j4=2 >%s datapath=%s/" % (fn_img, fnt_imgh_subsample,fn_img_path)
        scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
        cmd = '''
# (hx,hy,x,y,z)->transp->(x,y,z,hx,hy)->YFt3d->
# (kx,ky,kz,hx,hy)->transp->(hx,hy,kx,ky,kz)->Off2Ang3d_kxyz.x->
# (gamma, azim, kx,ky,kz) -> transp ->(kx,ky,kz,gamma,azim) -> YFt3d->
# (x,y,z,gamma,azim) -> transp -> (z,gamma,azim,x,y)\n'''
        scripts.append(cmd)
        cmd = "time Window3d <%s n1=1 n2=1 min1=0 min2=0 datapath=%s/ | YReorder reshape=2,3 mapping=2,1 >%s datapath=%s/ " % (fnt_imgh_subsample,path_tmp, fn_imgh0_zxy,fn_img_path)
        scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
        cmd1 = "time %s/YTransp12.x <%s reshape=2,5 >%s/t1.H datapath=%s/" % (dict_args['YANG_BIN'], fnt_imgh_subsample, path_tmp, path_tmp)
        cmd2 = "time %s/YFt3d <%s/t1.H nth=8 n1=%s n2=%s n3=%s sign1=1 sign2=1 sign3=1 >%s/t2.H IOtype=r2c datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, dict_args['nkx'],dict_args['nky'],dict_args['nkz'], path_tmp, path_tmp)
        cmd3 = "time %s/YTransp12.x <%s/t2.H reshape=3,5 >%s/t3.H datapath=%s/" % (dict_args['YANG_BIN'], path_tmp,path_tmp,path_tmp)
        scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
        scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
        scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3))
        fn_tmp_ang_kxyz = "%s/t-ang-kxyz.H" % path_tmp
        cmd = "\n# Now we have (hx,hy,kx,ky,kz) as input, do the (hx,hy)->(gamma, azim) mapping!\n"
        cmd += "time %s/Off2ang3dB_kxyz.x par=%s bforward=1 <%s/t3.H >%s datapath=%s/" % (dict_args['YANG_BIN'], dict_args['fn_off2ang_par'], path_tmp, fn_tmp_ang_kxyz, path_tmp)
        cmd1 = "time %s/YTransp12.x <%s reshape=2,5 >%s/t5.H datapath=%s/" % (dict_args['YANG_BIN'], fn_tmp_ang_kxyz, path_tmp, path_tmp)
        cmd2 = "time %s/YFt3d <%s/t5.H nth=8 sign1=-1 sign2=-1 sign3=-1 >%s/t6.H IOtype=c2r datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, path_tmp, path_tmp)
        # Compute nx,ny,nz of the subsampled offset image.
        n1_ss = (int(sepbase.get_sep_axis_params(fn_img,3)[0])+1)/2
        n2_ss = (int(sepbase.get_sep_axis_params(fn_img,4)[0])+1)/2
        n3_ss = int(sepbase.get_sep_axis_params(fn_img,5)[0])
        cmd3 = "time Window3d <%s/t6.H n1=%d n2=%d n3=%d >%s/t7.H IOtype=c2r datapath=%s/" % (path_tmp, n1_ss,n2_ss,n3_ss, path_tmp, path_tmp)
        # This time reshape=2,5, since (x,y,z,gamma,azim)=>(z,gamma,azim,x,y)
        cmd4 = "time %s/YTransp12.x <%s/t7.H reshape=2,5 >%s datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, fn_img_ang, fn_img_path)
        scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
        scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
        scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
        scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3))
        scripts.append(cmd4+CheckPrevCmdResultCShellScript(cmd4))
        #scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
        pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    # Now the angle gather image is ready, put back the correct axis dimensions.
    sepbase.put_sep_axis_params(fn_img_ang,4,ax_x_ss)
    sepbase.put_sep_axis_params(fn_img_ang,5,ax_y_ss)
  # Start computing the objective functions.
  if calc_dimg:
    if calc_ang_gather: fnt_dimg_out = fn_dimg_ang
    else: fnt_dimg_out = fn_dimg
  while True:
    job_identifier = 'objf-'+fn_img_base_wo_ext
    pbs_script_creator.CreateScriptForNewJob(job_identifier)
    # First check the log file of the last run to determine whether the input has been successful
    fn_log = pbs_script_creator.fn_log
    ## See if we've finished the computation and get meaningful result already, if so will exit the loop
    finished = False
    if os.path.isfile(fn_log):  # Extract the objective function value from the log, but search from backward.
      re_find = re.compile("ObjFuncValue=(.+)$")
      fp = open(fn_log,'r');log_txt_ls = fp.readlines();fp.close()
      for line in reversed(log_txt_ls):
        result = re_find.search(line)
        if result is not None:
          obj_func_value = float(result.group(1))
          break
      # Further check whether the dimg needs to be calculated
      if obj_func_value is None:  # Need to recompute
        pass
      else:
        if not calc_dimg:  # finish, no need to compute.
          break
        else: # Here check if the dimg has already been precomputed, if so, we can skip this file.
          file_error = pbs_util.CheckSephFileError(fnt_dimg_out,False)
          print file_error, fnt_dimg_out
          if file_error == 0:
            print "fnt_dimg_out file is good, skip: %s" % fnt_dimg_out
            break
          elif file_error == 1:
            sepbase.err("!fnt_dimg_out file is invalid (NaN): %s" % fnt_dimg_out)
          else:  # Needs to recompute the results.
            pass
    # Compute the obj func and dimg
    scripts = []
    cmd = 'time %s/CalcWemvaObjFunc.x par=%s img=%s b3D=%s wemva_type=%s datapath=%s/' % (dict_args['YANG_BIN'], dict_args['fn_wemva_objfunc_par'], fn_img, b3D, wemva_type, path_tmp)
    if calc_ang_gather:
      cmd += ' ang_img=%s imgh0_zxy=%s ' % (fn_img_ang, fn_imgh0_zxy)
    if calc_dimg: cmd += ' dimg=dimg.H '
    scripts.append(cmd+pbs_util.CheckPrevCmdResultCShellScript(cmd)+'\n')
    if calc_dimg:  # Needs to copy the output image out.
      scripts.append(pbs_script_creator.CmdCombineMultipleOutputSephFiles(['dimg.H'], fnt_dimg_out,""))
    scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
    pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    pbs_submitter.WaitOnAllJobsFinish(job_identifier)
    assert False
  # end for while
  print 'ObjFuncValue=%g' % obj_func_value
  # See if needs to convert dimg-ang back to dimg-off.
  if calc_ang_gather and calc_dimg:
    assert fnt_dimg_out == fn_dimg_ang
    while True:
      job_identifier = 'off-'+fn_img_base_wo_ext
      pbs_submitter.WaitOnAllJobsFinish(job_identifier)
      pbs_script_creator.CreateScriptForNewJob(job_identifier)
      file_error = pbs_util.CheckSephFileError(fn_dimg,False)
      if file_error == 0:
        print "The dimg ang2off gather file is good, skip: %s " % fn_dimg
        break
      else:  # Compute the off2angle gather
        cmd = '''
# (z,gamma,azim,x,y) -> Transp -> (x,y,z,gamma,azim) -> Ft3d ->
# (kx,ky,kz,gamma,azim) -> Transp -> (gamma,azim,kx,ky,kz) -> Off2Ang3d_kxyz.x ->
# (hxpad,hypad,kx,ky,kz) -> Transp -> (kx,ky,kz,hxpad,kypad) -> YFt3d ->
# (x,y,z,hx,hy) -> Transp -> (hx,hy,x,y,z)\n'''
        scripts.append(cmd)
        cmd1 = "time %s/YTransp12.x <%s reshape=3,5 >%s/t1.H datapath=%s/" % (dict_args['YANG_BIN'], fn_dimg_ang, path_tmp, path_tmp)
        cmd2 = "time %s/YFt3d <%s/t1.H nth=8 n1=%s n2=%s n3=%s sign1=1 sign2=1 sign3=1 >%s/t2.H IOtype=r2c datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, dict_args['nkx'],dict_args['nky'],dict_args['nkz'], path_tmp, path_tmp)
        cmd3 = "time %s/YTransp12.x <%s/t2.H reshape=3,5 >%s/t3.H datapath=%s/" % (dict_args['YANG_BIN'], path_tmp,path_tmp,path_tmp)
        scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
        scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
        scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3))
        fn_tmp_off_kxyz = "%s/t-off-kxyz.H" % path_tmp
        cmd = "\n# Now we have (gamma,azim,kx,ky,kz) as input, do the (hx,hy) <-- (gamma, azim) mapping!\n"
        scripts.append(cmd)
        cmd = "time %s/Off2ang3dB_kxyz.x par=%s bforward=0 <%s/t3.H >%s datapath=%s/" % (dict_args['YANG_BIN'], dict_args['fn_off2ang_par'], path_tmp, fn_tmp_off_kxyz, path_tmp)
        cmd1 = "time %s/YTransp12.x <%s reshape=2,5 >%s/t5.H datapath=%s/" % (dict_args['YANG_BIN'], fn_tmp_off_kxyz, path_tmp, path_tmp)
        cmd2 = "time %s/YFt3d <%s/t5.H nth=8 sign1=-1 sign2=-1 sign3=-1 >%s/t6.H IOtype=c2r datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, path_tmp, path_tmp)
        cmd3 = ("time Window3d <%s/t6.H n1=%d n2=%d n3=%d " 
                " n4=%d n5=%d >%s/t7.H datapath=%s/" % 
                (path_tmp, n1_ss,n2_ss,n3_ss, nhx,nhy, path_tmp, path_tmp))
        cmd4 = "time %s/YTransp12.x <%s/t7.H reshape=3,5 >%s datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, fn_dimg, path_out)
        scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
        scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
        scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
        scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3))
        scripts.append(cmd4+CheckPrevCmdResultCShellScript(cmd4))
  return obj_func_value

if __name__ == '__main__':
  Run(sys.argv)

