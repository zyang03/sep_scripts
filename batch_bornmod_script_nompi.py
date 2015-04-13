#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase

def self_doc():
  print 
  print 

## This program will do batch born-modeling from migrated subsurface-offset images.
## Basically, it performs all kinds of jobs that can be parallellized in the granularity of individual shots.

# Usage1:    *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 csou=csou.H
# Usage2:     User can also supply a list of ish_begs to start with
#             *.py pbs_template=pbs_script_tmpl.sh nfiles=1001 path_out=path_out prefix-img=img-waz3d queue=q35 nnodes=0 njobmax=5 ish_beglist=? nfiles_perbatch=10 csou=csou.H


def Run(argv):
  eq_args_from_cmdline,args = sepbase.parse_args(argv[1:])
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.WeiParamReader(dict_args)
  pbs_script_creator = pbs_util.PbsScriptCreator(param_reader)
  wei_scriptor = pbs_util.WeiScriptor(param_reader)
  print dict_args
  prefix = dict_args.get('prefix')  #, 'plane-waz3d')
  N = param_reader.nfiles
  n = param_reader.nfiles_perjob
  path_out = param_reader.path_out
  path_tmp = param_reader.path_tmp
  # Get the velocity file.
  fn_csou = param_reader.fn_csou
  fn_v3d = param_reader.fn_v3d
  ishot_list, nshot_list = pbs_util.GenShotsList(param_reader)
  # Initialize PbsSubmitter
  pbs_submitter = pbs_util.PbsSubmitter(zip(param_reader.queues, param_reader.queues_cap), param_reader.total_jobs_cap, dict_args['user'])

  while True:
    pbs_submitter.WaitOnAllJobsFinish(prefix)
    AllFilesComputed = True
    for ish,nsh in zip(ishot_list, nshot_list):  # For each job
      sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
      wei_scriptor.NewJob(sz_shotrange)
      #Append commands to the end of the created script file
      scripts = []
      scripts.append(wei_scriptor.CmdCpbvelForEachJob()+'\n')
      scripts.append(wei_scriptor.CmdCpbimgForEachJob()+'\n\n')
  
      # Do nfiles_per_batch shots at once
      script_needs_tobe_sumbitted = False
      for ii in range(0,nsh):
        ishl = ish+ii
        fn_shotfile = "%s/d-%s-%04d.H" % (path_out, prefix, ishl)
        # Here check if it has already been precomputed, if so, we can skip this file.
        file_error = pbs_util.CheckSephFileError(fn_shotfile,True)
        if file_error == 0:
          print "fn_shotfile is good, skip: %s" % fn_shotfile
          continue
        else:
          script_needs_tobe_sumbitted = True
        # First prepare the input csou/bvel/data etc.
        scripts.append(wei_scriptor.CmdCsouForEachShot(ishl)+"\n")
        scripts.append(wei_scriptor.CmdBornModelingPerShot(ishl)+'\n')
        # Copy the data out.
        cmd = "time Cp %s %s datapath=%s/" % (wei_scriptor.fnt_crec, fn_shotfile, path_out)
        scripts.append(cmd+pbs_util.CheckPrevCmdResultCShellScript(cmd)+'\n')
      scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
      if script_needs_tobe_sumbitted:
        AllFilesComputed = False
        pbs_script_creator.CreateScriptForNewJob(sz_shotrange)
        fn_script = pbs_script_creator.fn_script
        pbs_script_creator.AppendScriptsContent(scripts)
        pbs_submitter.SubmitJob(fn_script)
    # end for ish,nsh
    if AllFilesComputed: break
  # end while
  return


if __name__ == '__main__':
  Run(sys.argv)

