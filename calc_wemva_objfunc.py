#!/usr/bin/python
import commands,os,sys
import off2ang3d
import pbs_util
from pbs_util import CheckPrevCmdResultCShellScript
import re
import sepbase

## This program will compute the wemva objective function given an input image, it also computes the delta image (optional, if dimg= parameter is supplied. If calc_ang_gather=y, then will calc angle gather.
## It will submit jobs to pbs scheduling system.
# Usage: *.py param=wemva_obj.param pbs_template=pbs_script_tmpl.sh path_out=path_out queues=q35 njobmax=5 \
#             img=img.H b3D=n wemva_type=  [dimg=dimg.H]
# The underlying binary calling format:
# CalcWemvaObjFunc.x img=image.H [dimg=dimg.H] b3D=n wemva_type=61 


def Run(argv):
  '''Return the value of objective function calcualted.'''
  print "Run calc_wemva_objfunc script with params:", " ".join(argv)
  eq_args_from_cmdline,args = sepbase.parse_args(argv)
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.JobParamReader(dict_args)
  prefix = param_reader.prefix
  path_tmp = param_reader.path_tmp
  # Get the input image file.
  fn_img = os.path.abspath(dict_args['img'])
  # string fn_img_base_wo_ext serves as a single unique identifier.
  fn_img_path, fn_img_base_wo_ext, _ = pbs_util.SplitFullFilePath(fn_img)
  #path_out = param_reader.path_out
  path_out = fn_img_path
  # check if need to compute image perturbation.
  calc_dimg = False
  fn_dimg = dict_args.get('dimg')
  if fn_dimg is not None:
    calc_dimg = True
    fn_dimg = os.path.abspath(fn_dimg)
    fn_dimg_path, fn_dimg_base_wo_ext, _ = pbs_util.SplitFullFilePath(fn_dimg)
    fn_dimg_ang = "%s/%s-ang.H" % (fn_dimg_path, fn_dimg_base_wo_ext)
  b3D = dict_args['b3D']
  wemva_type = dict_args['wemva_type']
  # Check if need to compute angle gather
  wemva_parser = pbs_util.WemvaTypeParser(wemva_type,calc_dimg)
  calc_ang_gather = wemva_parser.calc_ang_gather
  calc_a2o = wemva_parser.calc_a2o
  # Initialize script_creators and PbsSubmitter.
  pbs_script_creator = pbs_util.PbsScriptCreator(param_reader)
  #assert param_reader.queues[0] != 'default'  # Put sep queue ahead of the default queue.
  pbs_submitter = pbs_util.PbsSubmitter(zip(param_reader.queues, param_reader.queues_cap), param_reader.total_jobs_cap, dict_args['user'])
  obj_func_value = None
  # Check input file validity.
  file_error = pbs_util.CheckSephFileError(fn_img,False)
  assert file_error == 0, "The input file: %s is incorrect: %d" % (fn_img, file_error)
  #nhx = int(sepbase.get_sep_axis_params(fn_img,1)[0])
  #nhy = int(sepbase.get_sep_axis_params(fn_img,2)[0])
  if calc_ang_gather:  # Need to compute angle gather first.
    fn_imgh0_hxyxyz = os.path.abspath(dict_args['bimgh0'])
    imgh0_path, imgh0_base, _ = pbs_util.SplitFullFilePath(fn_imgh0_hxyxyz)
    fn_imgh0_zxy = "%s/%s-h0zxy.H" % (imgh0_path, imgh0_base)
    fn_img_ang = "%s/%s-ang.H" % (fn_img_path, fn_img_base_wo_ext)
    fn_rmoplot_img = "%s/%s-ang-rmo.H" % (fn_img_path, fn_img_base_wo_ext)
    while True:
      # Check if the output file is already in place.
      file_error = pbs_util.CheckSephFileError(fn_img_ang,False)
      if file_error == 0:
        print "The image gather file is good, skip: %s " % fn_img_ang
        break
      else:  # Compute the angle gather
        cmd1 = "time Window3d <%s n1=1 n2=1 min1=0 min2=0 squeeze=n >%s datapath=%s/ " % (fn_img, fn_imgh0_hxyxyz, fn_img_path)
        cmd2 = "time %s/YReorder <%s reshape=2,4,5 mapping=3,2,1 >%s datapath=%s/ " % (dict_args['YANG_BIN'], fn_imgh0_hxyxyz, fn_imgh0_zxy,fn_img_path)
        sepbase.RunShellCmd(cmd1); sepbase.RunShellCmd(cmd2)
        eq_args_from_cmdline_cp = eq_args_from_cmdline.copy()
        eq_args_from_cmdline_cp['img'] = fn_img
        eq_args_from_cmdline_cp['imgout'] = fn_img_ang
        eq_args_from_cmdline_cp['off2ang'] = 'y'
        off2ang3d.Run(sepbase.GenCmdlineArgsFromDict(eq_args_from_cmdline_cp))
  # Start computing the objective functions.
  if calc_dimg:
    if calc_a2o: fnt_dimg_out = fn_dimg_ang
    else: fnt_dimg_out = fn_dimg
  while True:
    job_identifier = 'objf-'+fn_img_base_wo_ext
    pbs_script_creator.CreateScriptForNewJob(job_identifier)
    # First check the log file of the last run to determine whether the input has been successful
    fn_log = pbs_script_creator.fn_log
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
    fn_costcube = "%s/%s-costcube.H" % (fn_img_path, fn_img_base_wo_ext)
    cmd = 'time %s/CalcWemvaObjFunc.x par=%s img=%s b3D=%s wemva_type=%s datapath=%s/ cost_cube.H=%s' % (dict_args['YANG_BIN'], dict_args['fn_wemva_objfunc_par'], fn_img, b3D, wemva_type, path_out, fn_costcube)
    if calc_ang_gather:
      cmd += ' ang_img=%s imgh0_zxy=%s rmo.H=%s ' % (fn_img_ang, fn_imgh0_zxy, fn_rmoplot_img)
    if calc_dimg: cmd += ' dimg=%s '%fnt_dimg_out
    scripts.append(cmd+pbs_util.CheckPrevCmdResultCShellScript(cmd)+'\n')
    scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
    pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    pbs_submitter.WaitOnAllJobsFinish(prefix+'-'+job_identifier)
  # end for while
  print 'ObjFuncValue=%g' % obj_func_value
  # See if needs to convert dimg-ang back to dimg-off.
  if calc_a2o and calc_dimg:
    assert fnt_dimg_out == fn_dimg_ang
    while True:
      file_error = pbs_util.CheckSephFileError(fn_dimg,False)
      if file_error == 0:
        print "The dimg ang2off gather file is good, skip: %s " % fn_dimg
        break
      else:  # Compute the off2angle gather
        eq_args_from_cmdline_cp = eq_args_from_cmdline.copy()
        eq_args_from_cmdline_cp['img'] = fn_dimg_ang
        eq_args_from_cmdline_cp['imgout'] = fn_dimg
        eq_args_from_cmdline_cp['off2ang'] = 'n'
        off2ang3d.Run(sepbase.GenCmdlineArgsFromDict(eq_args_from_cmdline_cp))
  return obj_func_value


if __name__ == '__main__':
  Run(sys.argv)
