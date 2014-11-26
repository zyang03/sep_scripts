#!/usr/bin/python
import commands,os,sys
import pbs_util
from sepbase import *

def self_doc():
  print 
  print 

## This program will do batch born-modeling from migrated subsurface-offset images.
## Basically, it performs all kinds of jobs that can be parallellized in the granularity of individual shots.

# Usage1:    *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 nbatch=?
# Usage2:		 User can also supply a list of ish_begs to start with
#						 *.py pbs_template=pbs_script_tmpl.sh nfiles=1001 path=path_out prefix-img=img-waz3d queue=q35 nnodes=0 njobmax=5 ish_beglist=? nfiles_perbatch=10 csou=csou.H


if __name__ == '__main__':
  eq_args,args=parse_args(sys.argv[1:])
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = JobParamReader(dict_args)
  pbs_script_creator = pbs_util.PbsScriptCreator(dict_args)
	prefix = dict_args.get('preifix', 'd-plane-waz3d')
  N = param_reader.nfiles
	n = param_reader.nfiles_per_job
  path_out = param_reader.path_out
  path_tmp = param_reader.path_tmp
  # Get the velocity file and the shotsInfo file, etc.
  fn_csou = self.fn_csou if self.fn_csou else "csou-waz3d.H"  # Provide a default value.
  fn_v3d = self.fn_v3d
  ishot_list, nshot_list = pbs_util.GenShotsList(param_reader)

  for ish,nsh in zip(ishot_list, nshot_list):  # For each job
  	sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
    pbs_script_creator.CreateScript(fname_template_script, fn_script, fn_log, dict_args)
  	#Append commands to the end of the created script file
    fp_o = open(fn_script,'a')
    fp_o.write(pbs_script_creator.CmdCpbvelForEachJob(sz_shotrange)+'\n')
  	# Initialize PbsSubmitter
  	pbs_submitter = pbs_util.PbsSumbitter(zip(param_reader.queues, param_reader.queues_cap), param_reader.njobs_max, 'zyang03')
  
    shotfile_list = []
  	# Do nfiles_per_batch shots at once
  	for ii in range(0,nsh):
  		ishl = ish+ii
      # First prepare the input csou/bvel/data etc.
  	  fp_o.write(pbs_script_creator.CmdCsouForEachShot(ishl)+"\n")
      fn_shotfile = "%s/%s-%s.H" % (pathout, prefix, sz_shotrange)
      shotfile_list.append(fn_shotfile)
      fp_o.write(pbs_script_creator.CmdBornModelingPerShot(ishl)+'\n')
      # Copy the data out.
      fp_o.write("time Cp %s %s\n" % (pbs_script_creator.fnt_crec, fn_shotfile))

    # Final clean up, remove the files at tmp folder.
  	fp_o.write("\nfind %s/ -maxdepth 1 -type f -user zyang03 -exec rm {} \\;\n" % path_tmp)
  	fp_o.close()
  	
  	# Submit the job
    pbs_submitter.SubmitJob(fn_script)
  	print "Finished submission ish=%d / %d, %d" % (ish, nsh, N)

