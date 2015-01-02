#!/usr/bin/python
import commands,os,sys
import pbs_util
import re
import sepbase

## This program will compute the wemva objective function given an input image, it also computes the delta image (optional, if dimg= parameter is supplied.
## It will submit jobs to pbs scheduling system.
# Usage: *.py param=wemva_obj.param pbs_template=pbs_script_tmpl.sh path_out=path_out queues=q35 njobmax=5 \
#             img=img.H b3D=n wemva_type=  [dimg=dimg.H]

# The underlying binary calling format:
# CalcWemvaObjFunc.x img=image.H [dimg=dimg.H] b3D=n wemva_type=61 

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
  _, fn_img_basename = os.path.split(fn_img)
  fn_img_base_wo_ext = os.path.splitext(fn_img_basename)[0]
  # string fn_img_base_wo_ext serves as a single unique identifier.
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
  while True:
    job_identifier = 'objf-'+fn_img_base_wo_ext
    pbs_submitter.WaitOnAllJobsFinish(job_identifier)
    pbs_script_creator.CreateScriptForNewJob(job_identifier)
    # First check the log file of the last run to determine whether the input has been successful
    fn_log = pbs_script_creator.fn_log
    ## See if we've finished the computation and get meaningful result already, if so will exit the loop
    if os.path.isfile(fn_log):  # Extract the objective function value from the log.
      re_find = re.compile("ObjFuncValue=(.+)$",re.MULTILINE)
      fp = open(fn_log,'r'); log_txt = fp.read(); fp.close()
      result = re_find.search(log_txt)
      if result is not None:
        obj_func_value = float(result.group(1))
        # Further check whether the dimg needs to be calculated
        if not calc_dimg:  # finish
          break
        else:
          # Here check if the dimg has already been precomputed, if so, we can skip this file.
          file_error = pbs_util.CheckSephFileError(fn_dimg,False)
          print file_error, fn_dimg
          if file_error == 0:
            print "fn_imgh file is good, skip: %s" % fn_dimg
            break
          elif file_error == 1:
            sepbase.err("! fn_imgh file is invalid (NaN): %s" % fn_dimg)
            break
          else:  # Needs to recompute the results.
            pass
      else:
        print "log file exist: %s, but no ObjFuncValue info found!\n" % fn_log
    # Append commands to the end of the created script file
    scripts = []
    cmd = 'time %s/CalcWemvaObjFunc.x img=%s b3D=%s wemva_type=%s datapath=%s/' % (dict_args['YANG_BIN'], fn_img, b3D, wemva_type, path_tmp)
    if calc_dimg: cmd += ' dimg=dimg.H '
    scripts.append(cmd+pbs_util.CheckPrevCmdResultCShellScript(cmd)+'\n')
    if calc_dimg:  # Needs to copy the output image out.
      scripts.append(pbs_script_creator.CmdCombineMultipleOutputSephFiles(['dimg.H'], fn_dimg,""))
    scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
    pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
  # end for while
  print 'ObjFuncValue=%g' % obj_func_value
  return obj_func_value


if __name__ == '__main__':
  Run(sys.argv)

