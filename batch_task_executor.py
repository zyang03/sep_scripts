#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase

## This program will try to batch generate migration images (not limited to migrations).
## Basically, it performs wei jobs that can be parallellized in the granularity of individual shots.

# Usage1:    *.py param=waz3d.param pbs_template=pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix=hess-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 prefix=pf img=img_output.H
# Usage2:     User can also supply a list of ish_begs to start with
#             *.py ... ish_beglist=? ...


class BatchTaskExecutor:
  '''Run a batch job, with automatic fault recovery and dynamic work load
  splitting.'''
  def __init__(self,job_param_reader,pbs_submitter=None):
    self.job_param_reader = job_param_reader
    self.pbs_submitter = pbs_submitter
    if self.pbs_submitter is None:  # Provide a default job submitter
      self.pbs_submitter = pbs_util.PbsSubmitter(zip(job_param_reader.queues, job_param_reader.queues_cap), job_param_reader.total_jobs_cap)
    return

  def LaunchBatchTask(self, prefix, batch_task_composer):
    param_reader = self.job_param_reader
    pbs_submitter = self.pbs_submitter
    # Initialize script_creators and PbsSubmitter.
    pbs_script_creator = pbs_util.PbsScriptCreator(param_reader)
    # Main submission loop.
    AllFilesComputed = False
    while not AllFilesComputed:
      pbs_submitter.WaitOnAllJobsFinish(prefix+'-')
      AllFilesComputed = True
      subjobids, subjobfns_list = batch_task_composer.GetSubjobsInfo()
      assert len(subjobids) == len(subjobfns_list)
      for subjobid, subjobfns in zip(subjobids,subjobfns_list):  # For each job
        need_recompute = False
        # Here check if the designated files have already been precomputed, if so, we can skip this job.
        for fn in subjobfns:
          file_error = pbs_util.CheckSephFileError(fn,False)
          if file_error == 0:
            print "Target file is good, skip: %s" % fn
          else:
            if file_error == 1:
              print "! target file is invalid (NaN): %s" % fn
            else:
              print "! target file is missing or invalid (check binary part): %s" % fn
            need_recompute = True
            break
        if need_recompute:
          AllFilesComputed = False
          scripts, subjobname = batch_task_composer.GetSubjobScripts(subjobid)
          assert scripts is not None
          if not subjobname:  # Provide a default subjobname
            subjobname = "%s" % subjobid
          pbs_script_creator.CreateScriptForNewJob(subjobname)
          scripts.append(pbs_script_creator.CmdFinalCleanUpTempDir())
          pbs_submitter.SubmitJob(pbs_script_creator.AppendScriptsContent(scripts))
        # end if need_recompute
      # end for subjobsinfo
    # end for while
    print "Batch Task %s finished!" % prefix
    return


class BatchTaskComposer:
  '''Basically a list of tuples, each tuple is (subjobid, [fn1,fn2,...]), the
  list of filenames is the designated files that should be in place after the
  subjob finishes.'''
  def __init__(self):
    '''Constructor.'''
    return

  def GetSubjobScripts(self, subjobid):
    '''Return the scripts content for that subjob, and the subjob's name.
    Returns:
      scripts: a list of strings. Each strings should corresponds to one line
      of cmd.
      jobname: the designated jobname, if set=None, then the program will
      create a jobname automatically from subjobid.
    '''
    assert False, "!Implement me in the derived class."
    return

  def GetSubjobsInfo(self):
    '''Should return two lists, subjobids and subjobfns.'''
    assert False, "!Implement me in the derived class."
    return


class CombineTaskComposer(BatchTaskComposer):
  '''.'''
  def __init__(self, param_reader, input_seph_list, output_fn, combine_pars, datapath, initial_seph_domain_file)
    '''Constructor.'''
    BatchTaskComposer.__init__(self)
    self.param_reader = param_reader
    self.input_seph_list = input_seph_list
    self.output_fn = output_fn
    self.combine_pars = combine_pars
    self.datapath = datapath
    self.initial_seph_domain_file = initial_seph_domain_file
    return

  def GetSubjobScripts(self, subjobid):
    '''Return the scripts content for that subjob.'''
    assert subjobid == 0
    scriptor = JobScriptor(self.param_reader)
    scripts = []
    scripts.append(scriptor.CmdCombineMultipleOutputSephFiles(self.input_seph_list, self.output_fn, self.combine_pars, self.datapath, self.initial_seph_domain_file))
    return scripts,None

  def GetSubjobsInfo(self):
    '''Should return two lists, subjobids and subjobfns. In this case only one
    job and one file.
    '''
    return [0], [[output_fn]]


def CombineMultipleOutputSephFiles(batch_task_executor, local_seph_list, output_fn, combine_pars="", datapath=None, initial_seph_domain_file=None):
  bte = batch_task_executor
  param_reader = batch_task_executor.param_reader
  ctc = CombineTaskComposer(param_reader, local_seph_list, output_fn,
      combine_pars, datapath, initial_seph_domain_file)
  prefix = param_reader.prefix
  bte.LaunchBatchTask(prefix, ctc)
  return

