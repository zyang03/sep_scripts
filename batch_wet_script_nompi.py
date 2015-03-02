#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase

def self_doc():
  print 

## This program will try to batch generate velocity updates from wave-equation tomography operator.
# Usage1:    *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 vel=vel.H dimg=dimg.H prefix=pf dvel=output.H mode=tomadj,tomimit bimgh0=imgh0-hxyxyz.H
# Notice: The final output dvel will always be same size as the input vel, but for each shot, we can shrink the z dimension to save computation.

def Run(argv):
  print "Run script with params:", argv
  eq_args_from_cmdline,args = sepbase.parse_args(argv)
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.WeiParamReader(dict_args)
  
  prefix = dict_args['prefix']
  fn_dvel_final  = os.path.abspath(dict_args['dvel'])  # Final output (after stacking over all jobs).
  _, fn_base_wo_ext, _ = pbs_util.SplitFullFilePath(fn_dvel_final)
  # fn_base_wo_ext serves as a unique identifier.
  N = param_reader.nfiles
  n = param_reader.nfiles_perjob
  path_out = param_reader.path_out
  path_tmp = param_reader.path_tmp
  # Get the velocity file and the shotsInfo file, etc.
  fn_csou = param_reader.fn_csou
  fn_v3d = param_reader.fn_v3d
  fn_shotsinfo  = os.path.abspath(dict_args["shotsinfo"])
  shots_info = pbs_util.ShotsInfo(fn_shotsinfo)
  ishot_list, nshot_list = pbs_util.GenShotsList(param_reader)
  assert shots_info.TotNumShots() == N
  # Initialize script_creators and PbsSubmitter.
  pbs_script_creator = pbs_util.PbsScriptCreator(param_reader)
  wei_scriptor = pbs_util.WeiScriptor(param_reader)
  assert param_reader.queues[0] != 'default'  # Put sep queue ahead of the default queue.
  pbs_submitter = pbs_util.PbsSubmitter(zip(param_reader.queues, param_reader.queues_cap), param_reader.total_jobs_cap, dict_args['user'])
  # See if specify image/Hessian/dvel dimensions in cmdline, don't further shrink x,y direction, but z domain can be shrinked to reduce the computational cost in a layer-stripping type of strategy.
  [zmin_cmdl,zmax_cmdl] = param_reader.g_output_image_domain[4:6]
  # Check tomadj or tomimit
  mode = dict_args['mode']
  if mode == 'tomadj':
    pass
  elif mode == 'tomimit':
    fn_bimgh0 = os.path.abspath(dict_args['bimgh0'])
  else:  assert False
  # First check if the final dvel exists, if so we can return the result directly.
  if pbs_util.CheckSephFileError(fn_dvel_final,False)==0:
    print "final dvel already in place, skip: %s" % fn_dvel_final
    return
  # Main submission loop.
  AllFilesComputed = False
  while not AllFilesComputed:
    pbs_submitter.WaitOnAllJobsFinish()
    AllFilesComputed = True
    fn_output_list_all = []  # Store names of all output files (one for each job)
    for ish,nsh in zip(ishot_list, nshot_list):  # For each job
      sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
      wei_scriptor.NewJob(sz_shotrange)
      fn_output  = "%s/%s-%s.H"  %(path_out, fn_base_wo_ext, sz_shotrange)
      fn_output_list_all.append(fn_output)
      # Here check if it has already been precomputed, if so, we can skip this file.
      file_error = pbs_util.CheckSephFileError(fn_output,False)
      if file_error == 0:
        print "Current fn_output is good, skip: %s" % fn_output
        continue
      elif file_error == 1:
        print "! fn_output is invalid (NaN): %s" % fn_output
      else: pass
      # Needs to [re-]compute this job.
      AllFilesComputed = False
      # Append commands to the end of the created script file
      scripts = []
      scripts.append(wei_scriptor.CmdCpbvelForEachJob(zmax_cmdl)+'\n')
      scripts.append(wei_scriptor.CmdCpdimgForEachJob()+'\n')
      if mode == 'tomimit':
        scripts.append(wei_scriptor.CmdCpbimgh0ForEachJob()+'\n')
      scripts.append('\n')
      # Do nfiles_per_batch shots at once
      for ii in range(0,nsh):
        ishl = ish+ii
        # First prepare the input csou/data etc.
        scripts.append(wei_scriptor.CmdCsouForEachShot(ishl))
        fn_shotfile = shots_info.ShotFileNameAt(ishl)
        if mode == 'tomimit':
          cmd2 = wei_scriptor.CmdWetomoimitPerShot(ishl)
        else:  # conventional tomadj
          scripts.append(wei_scriptor.CmdCpCrecForEachShot(ishl, fn_shotfile))
          cmd2 = wei_scriptor.CmdWetomoPerShot(ishl)
        scripts.append(cmd2+ "\n");
      # end for ish,nsh
      # Now copy the results cubes out, if multiple shots then combine them first
      fnt_output_list = wei_scriptor.fnt_output_list
      # For fn_dvel, Axis 1,2,3 are (x,y,z)
      scripts.append(
          pbs_script_creator.CmdCombineMultipleOutputSephFiles(
              fnt_output_list, fn_output, "", None, wei_scriptor.fnt_bvel))
      scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
      pbs_script_creator.CreateScriptForNewJob('%s-%s'%(sz_shotrange, fn_base_wo_ext))
      pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    # end for ish,nsh
  # end while not AllFilesComputed
  # Now combine all dvel files together, use a new pbs_submitter, need to use the non-default queue.
  pbs_submitter = pbs_util.PbsSubmitter([(param_reader.queues[0], param_reader.queues_cap[0])], None, dict_args['user'])
  scripts = []; combine_pars = ""
  #if xmin_cmdl is not None: combine_pars = "oe1=%g,%g oe2=%g,%g ndim=3" % (xmin_cmdl,xmax_cmdl,ymin_cmdl,ymax_cmdl)
  scripts.append(pbs_script_creator.CmdCombineMultipleOutputSephFiles(fn_output_list_all, fn_dvel_final, combine_pars,None,param_reader.fn_v3d))
  pbs_script_creator.CreateScriptForNewJob(fn_base_wo_ext)
  pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
  pbs_submitter.WaitOnAllJobsFinish(fn_base_wo_ext)
  # Check if the output is valid.
  file_error = pbs_util.CheckSephFileError(fn_dvel_final,True)
  if file_error == 0:
    print "Output file is good: %s" % fn_dvel_final
  elif file_error == 1:
    assert False, "! fn_output is invalid (NaN): %s" % fn_output
  else:
    assert False, "! fn_output is invalid: %s" % fn_output
  return

if __name__ == '__main__':
  Run(sys.argv)

