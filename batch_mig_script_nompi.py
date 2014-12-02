#!/usr/bin/python
import commands,os,sys
import pbs_util
from sepbase import *

def self_doc():
  print 
  print 

## This program will try to batch generate migration images (not limited to migrations).
## Basically, it performs all kinds of jobs that can be parallellized in the granularity of individual shots.

# Usage1:    *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 nbatch=?
# Usage2:		 User can also supply a list of ish_begs to start with
#						 *.py pbs_template=pbs_script_tmpl.sh nfiles=1001 path=path_out prefix-img=img-waz3d queue=q35 nnodes=0 njobmax=5 ish_beglist=? nfiles_perbatch=10 csou=csou.H


if __name__ == '__main__':
  eq_args,args=parse_args(sys.argv[1:])
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = JobParamReader(dict_args)
  pbs_script_creator = pbs_util.PbsScriptCreator(dict_args)
	prefix = dict_args.get('preifix', 'imgh-waz3d')
  N = param_reader.nfiles
	n = param_reader.nfiles_per_job
  path_out = param_reader.path_out
  path_tmp = param_reader.path_tmp
  # Get the velocity file and the shotsInfo file, etc.
  fn_csou = self.fn_csou if self.fn_csou else "csou-waz3d.H"  # Provide a default value.
  fn_v3d = self.fn_v3d
  fn_shotsInfo	= os.path.abspath(dict_args["shotsInfo"])
  shots_info = ShotsInfo(fn_shotsInfo)
  ishot_list, nshot_list = pbs_util.GenShotsList(param_reader)

  # See if specify image/Hessian dimensions in cmdline
  [xmin_cmdl,xmax_cmdl, ymin_cmdl,ymax_cmdl, zmin_cmdl,zmax_cmdl] = param_reader.g_output_image_domain
  for ish,nsh in zip(ishot_list, nshot_list):  # For each job
  	sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
    pbs_script_creator.CreateScript(fname_template_script, fn_script, fn_log, dict_args)
  	#Append commands to the end of the created script file
    fp_o = open(fn_script,'a')
    fp_o.write(pbs_script_creator.CmdCpbvelForEachJob(sz_shotrange)+'\n')
  	# Initialize PbsSubmitter
  	pbs_submitter = pbs_util.PbsSumbitter(zip(param_reader.queues, param_reader.queues_cap), param_reader.njobs_max, 'zyang03')
  
  	xmin_g = xmax_g = ymin_g = ymax_g = None
  	# Do nfiles_per_batch shots at once
  	for ii in range(0,nsh):
  		ishl = ish+ii
      # First prepare the input csou/bvel/data etc.
  	  fp_o.write(pbs_script_creator.CmdCsouForEachShot(ishl)+"\n")
      fn_shotfile = shots_info.ShotFileNameAt(ishl)
      fp_o.write(pbs_script_creator.CmdCpCrecForEachShot(ishl, fn_shotfile)+'\n')
  		xmin_1, xmax_1, ymin_1, ymax_1 = shots_info.ShotFileApertureAt(ishl)
  		# Find the overlap between 1shot imaging aperture and the final imaging domain
      if xmin_cmdl is not None:
  			xmin_1 = max(xmin_1,xmin_cmdl); xmax_1 = min(xmax_1,xmax_cmdl)
      if ymin_cmdl is not None:
  			ymin_1 = max(ymin_1,ymin_cmdl); ymax_1 = min(ymax_1,ymax_cmdl)
  		# Calculate the image/Hessian/Data with subsurf offset.
      cmd2 = pbs_script_creator.CmdMigration(ishl,
          (xmin_1,xmax_1, ymin_1,ymax_1, zmin_cmdl,zmax_cmdl))
  		fp_o.write("echo " + cmd2+ "\n");  fp_o.write("time " + cmd2+"\n\n")

      if xmin_g is None:
  			xmin_g = xmin_1; xmax_g = xmax_1; ymin_g = ymin_1; ymax_g = ymax_1
  		else:
  			xmin_g = min(xmin_1,xmin_g); xmax_g = max(xmax_g,xmax_1)
        ymin_g = min(ymin_1,ymin_g); ymax_g = max(ymax_g,ymax_1)
  	#Now copy the results cubes out, if multiple shots then combine them first
    fn_imgh = pbs_script_creator.fn_imgh
    fnt_imgh_list = pbs_script_creator.fnt_imgh_list
  	# For fn_imgh, Axis 3,4,5 are (x,y,z)
    fp_o.write(pbs_script_creator.CmdCombineMultipleOutputSepHFiles(
        sz_shotrange, fnt_imgh_list, fn_imgh, "oe3=%g,%g oe4=%g,%g ndim=5" % (xmin_g,xmax_g,ymin_g,ymax_g)))
  	fp_o.write(cmd)
  	# Last step, remove the files at tmp folder.
  	fp_o.write("\nfind %s/ -maxdepth 1 -type f -user zyang03 -exec rm {} \\;\n" % path_tmp)
  	fp_o.close()
  	# Submit the job
  	pbs_submitter.SubmitJob(fn_script)
  	print "Finished submission ish=%d / %d, %d" % (ish, nsh, N)


