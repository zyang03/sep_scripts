#!/usr/bin/python
import commands,os,sys
import pbs_util
from pbs_util import CheckPrevCmdResultCShellScript
import re
import sepbase

## This program will compute the wemva objective function given an input image, it also computes the delta image (optional, if dimg= parameter is supplied. If calc_ang_gather=y, then will calc angle gather.
## It will submit jobs to pbs scheduling system.
# Usage: *.py param=paramfile.param pbs_template=pbs_script_tmpl.sh path_out=path_out queues=q35 \
#             off2ang=y/n img=input_img.H imgout=.H kz_xy=n
# If calculate angle gather and kz_xy=n, then 
# (hx,hy,x,y,z)->transp->(x,y,z,hx,hy)->YFt3d->
# (kx,ky,kz,hx,hy)->transp->(hx,hy,kx,ky,kz)->Off2Ang3d_kxyz.x->
# (gamma, azim, kx,ky,kz) -> transp ->(kx,ky,kz,gamma,azim) -> YFt3d->
# (x,y,z,gamma,azim) -> transp -> (z,gamma,azim,x,y) -> RMO ->
# (z,gamma,azim,x,y) -> Transp -> (x,y,z,gamma,azim) -> Ft3d ->
# (kx,ky,kz,gamma,azim) -> Transp -> (gamma,azim,kx,ky,kz) -> Off2Ang3d_kxyz.x ->
# (hx,hy,kx,ky,kz) -> Transp -> (kx,ky,kz,hx,ky) -> YFt3d ->
# (x,y,z,hx,hy) -> Transp -> (hx,hy,x,y,z)
# That is 9 Transps, 4 YFt3d and 1 Off2Ang_kxyz Mapping

# Else if calculate angle gather and kz_xy=y, then 
# (hx,hy,x,y,z)->YReorder->(hx,hy,z,x,y)->YFt3d->
# (hx,hy,kz,x,y)->Off2Ang3d_kz_xy.x->
# (gamma, azim, kz,x,y) -> YFt3d-> (gamma,azim,z,x,y) -> YReorder (z,gamma,azim,x,y) -> RMO ->
# (z,gamma,azim,x,y) -> YReorder -> (gamma,azim,z,x,y) -> Ft3d ->
# (gamma,azim,kz,x,y) ->  Off2Ang3d_kz_xy.x ->
# (hx,hy, kz,x,y) -> YFt3d -> (hx,hy, z,x,y) -> YReorder -> (hx,hy,x,y,z)
# That is 4 Reorder, 4 YFt3d and 1 Off2Ang_kz_xy.x Mapping

def Run(argv):
  '''Do 3d off2ang3d using fourier domain mapping suggested by Biondi & Tisserant 2003.'''
  print "Run the off2ang3d script with params:", " ".join(argv)
  eq_args_from_cmdline,args = sepbase.parse_args(argv)
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.JobParamReader(dict_args)
  prefix = param_reader.prefix
  path_out = param_reader.path_out
  path_tmp = param_reader.path_tmp
  boff2ang = sepbase.ParseBooleanString(dict_args['off2ang'])
  b_kz_xy = sepbase.ParseBooleanString(dict_args['kz_xy'])
  print "kz_xy=",b_kz_xy
  # Check input file validity.
  fn_img = os.path.abspath(dict_args['img'])
  file_error = pbs_util.CheckSephFileError(fn_img,False)
  assert file_error == 0, "The input file: %s is incorrect: %d" % (fn_img, file_error)
  # string fn_img_base_wo_ext serves as a single unique identifier.
  fn_img_path, fn_img_base_wo_ext, _ = pbs_util.SplitFullFilePath(fn_img)
  fn_img_out = os.path.abspath(dict_args['imgout'])
  # Initialize script_creators and PbsSubmitter.
  pbs_script_creator = pbs_util.PbsScriptCreator(param_reader)
  pbs_submitter = pbs_util.PbsSubmitter(zip(param_reader.queues, param_reader.queues_cap),param_reader.total_jobs_cap, dict_args['user'])
  if boff2ang:  # Then input is off img.
    job_identifier = 'ang-' + fn_img_base_wo_ext
    ax_x = sepbase.get_sep_axis_params(fn_img,3); ax_y = sepbase.get_sep_axis_params(fn_img,4)
    ax_z = sepbase.get_sep_axis_params(fn_img,5)
    pbs_script_creator.CreateScriptForNewJob(job_identifier); scripts = []
    if b_kz_xy: # do the 3-D FFT transform with dip info.
      cmd = '''
# (hx,hy,x,y,z)->YReorder->(hx,hy,z,x,y)->YFt3d->
# (hx,hy,kz,x,y)->Off2Ang3d_kz_xy.x->
# (gamma, azim, kz,x,y) -> YFt3d-> (gamma,azim,z,x,y) -> YReorder -> (z,gamma,azim,x,y)\n'''
      scripts.append(cmd)
      cmd1 = "time %s/YReorder <%s reshape=2,4,5 mapping=1,3,2 >%s/t1.H datapath=%s/" % (dict_args['YANG_BIN'], fn_img, path_tmp, path_tmp)
      cmd2 = "time %s/YFt3d <%s/t1.H nth=8 n3=%s sign1=0 sign2=0 sign3=1 >%s/t2.H IOtype=r2c datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, dict_args['nkz'], path_tmp, path_tmp)
      scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
      scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
      fn_tmp_ang_kz_xy = "%s/t-ang-kz_xy.H" % path_tmp
      cmd = "\n# Now we have (hx,hy,kz,x,y) as input, do the (hx,hy)->(gamma, azim) mapping!\n"
      cmd += "time %s/Off2ang3dB_kz_xy.x par=%s bforward=1 <%s/t2.H >%s datapath=%s/" % (dict_args['YANG_BIN'], dict_args['fn_off2ang_par'], path_tmp, fn_tmp_ang_kz_xy, path_tmp)
      cmd1 = "time %s/YFt3d <%s nth=8 sign1=0 sign2=0 sign3=-1 >%s/t6.H IOtype=c2r datapath=%s/" % (dict_args['YANG_BIN'], fn_tmp_ang_kz_xy, path_tmp, path_tmp)
      cmd2 = "time Window3d <%s/t6.H n3=%s >%s/t7.H datapath=%s/" % (path_tmp, ax_z[0], path_tmp, path_tmp)
      cmd3 = "time %s/YReorder <%s/t7.H reshape=2,3,5 mapping=2,1,3 >%s datapath=%s/ verb=n" % (dict_args['YANG_BIN'], path_tmp, fn_img_out, fn_img_path)
      scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
      scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
      scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
      scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3))
    else:
      cmd = '''
# (hx,hy,x,y,z)->transp->(x,y,z,hx,hy)->YFt3d->
# (kx,ky,kz,hx,hy)->transp->(hx,hy,kx,ky,kz)->Off2Ang3d_kxyz.x->
# (gamma, azim, kx,ky,kz) -> transp ->(kx,ky,kz,gamma,azim) -> YFt3d->
# (x,y,z,gamma,azim) -> transp -> (z,gamma,azim,x,y)\n'''
      scripts.append(cmd)
      cmd1 = "time %s/YTransp12.x <%s reshape=2,5 >%s/t1.H datapath=%s/" % (dict_args['YANG_BIN'], fn_img, path_tmp, path_tmp)
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
      cmd3 = "time Window3d <%s/t6.H n1=%s n2=%s n3=%s >%s/t7.H datapath=%s/" % (path_tmp, ax_x[0],ax_y[0],ax_z[0], path_tmp, path_tmp)
      # This time reshape=2,5, since (x,y,z,gamma,azim)=>(z,gamma,azim,x,y)
      cmd4 = "time %s/YTransp12.x <%s/t7.H reshape=2,5 >%s datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, fn_img_out, fn_img_path)
      scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
      scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1)); scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
      scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3)); scripts.append(cmd4+CheckPrevCmdResultCShellScript(cmd4))
    # end if kz_xy
    scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
    pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    pbs_submitter.WaitOnAllJobsFinish(prefix+'-'+job_identifier)
    # Now the angle gather image is ready, put back the correct axis dimensions.
    sepbase.put_sep_axis_params(fn_img_out,1,ax_z)
    sepbase.put_sep_axis_params(fn_img_out,4,ax_x)
    sepbase.put_sep_axis_params(fn_img_out,5,ax_y)
  else:  # Compute the off gather, then input is ang img.
    ax_x = sepbase.get_sep_axis_params(fn_img,4); ax_y = sepbase.get_sep_axis_params(fn_img,5)
    ax_z = sepbase.get_sep_axis_params(fn_img,1)
    job_identifier = 'off-' + fn_img_base_wo_ext
    pbs_script_creator.CreateScriptForNewJob(job_identifier); scripts = []
    if b_kz_xy: # do the 3-D FFT transform with dip info.
      cmd = '''
# (z,gamma,azim,x,y) -> YReorder -> (gamma,azim,z,x,y) -> Ft3d ->
# (gamma,azim,kz,x,y) ->  Off2Ang3d_kz_xy.x ->
# (hx,hy, kz,x,y) -> YFt3d -> (hx,hy, z,x,y) -> YReorder -> (hx,hy,x,y,z)\n'''
      scripts.append(cmd)
      cmd1 = "time %s/YReorder <%s reshape=1,3,5 mapping=2,1,3 >%s/t1.H datapath=%s/ verb=n" % (dict_args['YANG_BIN'], fn_img, path_tmp, path_tmp)
      cmd2 = "time %s/YFt3d <%s/t1.H nth=8 n3=%s sign1=0 sign2=0 sign3=1 >%s/t2.H IOtype=r2c datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, dict_args['nkz'], path_tmp, path_tmp)
      scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
      scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
      fn_tmp_off_kz_xy = "%s/t-off-kz_xy.H" % path_tmp
      cmd = "\n# Now we have (gamma,azim, kz,x,y) as input, do the (hx,hy) <-- (gamma, azim) mapping!\n"
      scripts.append(cmd)
      cmd = "time %s/Off2ang3dB_kz_xy.x par=%s bforward=0 <%s/t2.H >%s datapath=%s/" % (dict_args['YANG_BIN'], dict_args['fn_off2ang_par'], path_tmp, fn_tmp_off_kz_xy, path_tmp)
      cmd1 = "time %s/YFt3d <%s nth=8 sign1=0 sign2=0 sign3=-1 >%s/t6.H IOtype=c2r datapath=%s/" % (dict_args['YANG_BIN'], fn_tmp_off_kz_xy, path_tmp, path_tmp)
      cmd2 = ("time Window3d <%s/t6.H n3=%s >%s/t7.H datapath=%s/" %
              (path_tmp, ax_z[0], path_tmp, path_tmp))
      cmd3 = "time %s/YReorder <%s/t7.H reshape=2,3,5 mapping=1,3,2 >%s datapath=%s/ verb=n" % (dict_args['YANG_BIN'], path_tmp, fn_img_out, path_out)
      scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
      scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1))
      scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
      scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3))
    else:  # do the 5-D mapping
      cmd = '''
# (z,gamma,azim,x,y) -> Transp -> (x,y,z,gamma,azim) -> Ft3d ->
# (kx,ky,kz,gamma,azim) -> Transp -> (gamma,azim,kx,ky,kz) -> Off2Ang3d_kxyz.x ->
# (hxpad,hypad,kx,ky,kz) -> Transp -> (kx,ky,kz,hxpad,kypad) -> YFt3d ->
# (x,y,z,hx,hy) -> Transp -> (hx,hy,x,y,z)\n'''
      scripts.append(cmd)
      cmd1 = "time %s/YTransp12.x <%s reshape=3,5 >%s/t1.H datapath=%s/" % (dict_args['YANG_BIN'], fn_img, path_tmp, path_tmp)
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
      cmd3 = ("time Window3d <%s/t6.H n1=%s n2=%s n3=%s >%s/t7.H datapath=%s/" %
              (path_tmp, ax_x[0],ax_y[0],ax_z[0], path_tmp, path_tmp))
      cmd4 = "time %s/YTransp12.x <%s/t7.H reshape=3,5 >%s datapath=%s/" % (dict_args['YANG_BIN'], path_tmp, fn_img_out, path_out)
      scripts.append(cmd+CheckPrevCmdResultCShellScript(cmd))
      scripts.append(cmd1+CheckPrevCmdResultCShellScript(cmd1)); scripts.append(cmd2+CheckPrevCmdResultCShellScript(cmd2))
      scripts.append(cmd3+CheckPrevCmdResultCShellScript(cmd3)); scripts.append(cmd4+CheckPrevCmdResultCShellScript(cmd4))
    # end if kz_xy
    scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
    pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    pbs_submitter.WaitOnAllJobsFinish(prefix+'-'+job_identifier)
    print "put right axis into fn_img_off_out: %s " % fn_img_out
    # Now the off gather image is ready, put back the correct axis dimensions.
    sepbase.put_sep_axis_params(fn_img_out,3,ax_x)
    sepbase.put_sep_axis_params(fn_img_out,4,ax_y)
    sepbase.put_sep_axis_params(fn_img_out,5,ax_z)
  # Check the integrity of the output.
  file_error = pbs_util.CheckSephFileError(fn_img_out,False)
  assert file_error == 0, "!!The output file: %s is incorrect: %d" % (fn_img_out, file_error)
  return


if __name__ == '__main__':
  Run(sys.argv)
