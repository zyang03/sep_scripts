#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase

## This program will try to batch generate migration images (not limited to migrations).
## Basically, it performs wei jobs that can be parallellized in the granularity of individual shots.

# Usage1:    *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 prefix=pf img=img_output.H
# Usage2:     User can also supply a list of ish_begs to start with
#             *.py ... ish_beglist=? ...

def Run(argv):
  print "Run script with params:", argv
  eq_args_from_cmdline,args = sepbase.parse_args(argv)
  dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.WeiParamReader(dict_args)
  prefix = dict_args['prefix']
  fn_imgh_final  = os.path.abspath(dict_args['img'])
  datapath_final, fn_imgh_final_basename = os.path.split(fn_imgh_final)
  fn_base_wo_ext = os.path.splitext(fn_imgh_final_basename)[0]
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
  # See if specify image/Hessian dimensions in cmdline
  [xmin_cmdl,xmax_cmdl, ymin_cmdl,ymax_cmdl, zmin_cmdl,zmax_cmdl] = param_reader.g_output_image_domain
  # First check if the final imgh exists
  if pbs_util.CheckSephFileError(fn_imgh_final,False)==0:
    print "final image already in place, skip: %s" % fn_imgh_final
    return
  # Main submission loop.
  AllFilesComputed = False
  while not AllFilesComputed:
    pbs_submitter.WaitOnAllJobsFinish()
    AllFilesComputed = True
    fn_imgh_list_all = []
    for ish,nsh in zip(ishot_list, nshot_list):  # For each job
      sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
      wei_scriptor.NewJob(sz_shotrange)
      fn_imgh  = "%s/%s-%s.H"  %(path_out, fn_base_wo_ext, sz_shotrange)
      fn_imgh_list_all.append(fn_imgh)
      # Here check if it has already been precomputed, if so, we can skip this file.
      file_error = pbs_util.CheckSephFileError(fn_imgh,False)
      if file_error == 0:
        print "fn_imgh file is good, skip: %s" % fn_imgh
        continue
      else:
        if file_error == 1:
          print "! fn_imgh file is invalid (NaN): %s" % fn_imgh
      AllFilesComputed = False
      # Append commands to the end of the created script file
      scripts = []
      scripts.append(wei_scriptor.CmdCpbvelForEachJob()+'\n\n')    
      xmin_g = xmax_g = ymin_g = ymax_g = None
      # Do nfiles_per_batch shots at once
      for ii in range(0,nsh):
        ishl = ish+ii
        # First prepare the input csou/data etc.
        scripts.append(wei_scriptor.CmdCsouForEachShot(ishl))
        fn_shotfile = shots_info.ShotFileNameAt(ishl)
        scripts.append(wei_scriptor.CmdCpCrecForEachShot(ishl, fn_shotfile))
        xmin_1, xmax_1, ymin_1, ymax_1 = shots_info.ShotFileApertureAt(ishl)
        # Find the overlap between 1shot imaging aperture and the final imaging domain
        xmin_1,xmax_1,ymin_1,ymax_1 = pbs_util.OverlapRectangle([xmin_1,xmax_1,ymin_1,ymax_1],[xmin_cmdl,xmax_cmdl,ymin_cmdl,ymax_cmdl])
        # Calculate the image/Hessian/Data with subsurf offset.
        cmd2 = wei_scriptor.CmdMigrationPerShot(ishl,
            (xmin_1,xmax_1, ymin_1,ymax_1, zmin_cmdl,zmax_cmdl))
        scripts.append(cmd2+ "\n");
        xmin_g,xmax_g,ymin_g,ymax_g = pbs_util.UnionRectangle([xmin_1,xmax_1,ymin_1,ymax_1],[xmin_g,xmax_g,ymin_g,ymax_g])
      # End for ishl. Now copy the results cubes out, if multiple shots then combine them first
      fnt_imgh_list = wei_scriptor.fnt_output_list
      # For fn_imgh, Axis 3,4,5 are (x,y,z)
      scripts.append(
          pbs_script_creator.CmdCombineMultipleOutputSephFiles(
              fnt_imgh_list, fn_imgh,
              "oe3=%g,%g oe4=%g,%g ndim=5" % (xmin_g,xmax_g,ymin_g,ymax_g), path_out))
      scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
      pbs_script_creator.CreateScriptForNewJob('%s-%s'%(sz_shotrange,fn_base_wo_ext))
      pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
    # end for ish,nsh
  # end for while
  # Now combine all imgh files together, use a new pbs_submitter, need to use the non-default queue.
  pbs_submitter = pbs_util.PbsSubmitter([(param_reader.queues[0], param_reader.queues_cap[0])], None, dict_args['user'])
  scripts = []
  combine_pars = ""
  if xmin_cmdl is not None:
    combine_pars = "oe3=%g,%g oe4=%g,%g ndim=5" % (xmin_cmdl,xmax_cmdl,ymin_cmdl,ymax_cmdl)
  scripts.append(pbs_script_creator.CmdCombineMultipleOutputSephFiles(
      fn_imgh_list_all, fn_imgh_final, combine_pars, datapath_final))
  pbs_script_creator.CreateScriptForNewJob("%s" % fn_base_wo_ext)
  pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
  pbs_submitter.WaitOnAllJobsFinish()
  return


if __name__ == '__main__':
  Run(sys.argv)

