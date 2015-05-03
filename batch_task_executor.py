#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase
from os.path import abspath


class BatchTaskExecutor:
  '''Run a batch job, with automatic fault recovery,
  Basically, it performs jobs that can be parallellized in the granularity of individual shots,
  like wave-equation migration and tomography operators.
  '''

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
    rounds = 0
    while not AllFilesComputed:
      if rounds >= 5:
        sepbase.err('!The batch_task %s has been iterated over %d rounds, but not fully completed. Check your job description!')
      rounds += 1
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
  '''NOTICE: This is the interface that you (as a user) needs to program, which implements the batch task/job description.
  The way the batch task is defined is explained as follows (a migration example will be used in the explaination):
  1): For each batch task, it will be divided into multiple (>=1) subjobs.
      How the batch task will be divided is up to the design choice of the user.
      Each subjob is considered to be the workload submitted to a single computer node as one PBS job.
      In the example of WE-migration of 50 shots data. One possible way to divide this task is to break the 50 shots into 10 groups, and we create 10 subjobs, with each subjob being responsible for migrating the 5 shots within the corresponding shots group.
  2): For each subjob, the user is responsible to provide the actual computation recipe that will perform the expected work, in the form of shell script lines.
      For the migration example, the computation recipe for the first subjob (subjobid=0) can be sth like:
      ```
        mybin/Migration.x vel=vel.H <dat-shot0.H >img0.H
        mybin/Migration.x vel=vel.H <dat-shot1.H >img1.H
        mybin/Migration.x vel=vel.H <dat-shot2.H >img2.H
        mybin/Migration.x vel=vel.H <dat-shot3.H >img3.H
        mybin/Migration.x vel=vel.H <dat-shot4.H >img4.H
      ```
      Note that here all the boiler-plates in the original PBS script has been taken care by the framework, and the user does not need to worry about it.
  '''
  def __init__(self):
    '''Dummy constructor.'''
    return

  def GetSubjobScripts(self, subjobid):
    '''Implement this interface to specify the computation recipe for each subjob.
    Returns:
      scripts: a list of strings. Each strings should corresponds to one line of cmdline execution.
      jobname: the designated jobname, if set=None, then the framework will generate a jobname automatically based on subjobid.
    '''
    assert False, "!Implement me in the derived class."
    return

  def GetSubjobsInfo(self):
    '''Implement this interface to specify the subjobs description.
    The function should return two lists: subjobids and subjobfns.
    Returns:
      subjobids: is a list of unique interger ids, each one refers to a subjob.
      subjobfns: is a list of lists (string-type). Each sublist contains multiple (>=1) filenames that are the expected outcome of executing the corresponding subjob.
    In the migration example, subjobids=[0,1,2,3,...,9], and subjobfns will be sth like:
    [ [img0.H,img1.H,...img4.H], [img5.H,img6.H,...,img9.H], ... ]
    Basically, the list of filenames in subjobfns are the designated files that should be in place after that subjob finishes.
    '''
    assert False, "!Implement me in the derived class."
    return


class CombineTaskComposer(BatchTaskComposer):
  '''.'''
  def __init__(self, param_reader, input_seph_list, output_fn, combine_pars, datapath, initial_seph_domain_file):
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
    scriptor = pbs_util.JobScriptor(self.param_reader)
    scripts = []
    scripts.append(scriptor.CmdCombineMultipleOutputSephFiles(self.input_seph_list, self.output_fn, self.combine_pars, self.datapath, self.initial_seph_domain_file))
    return scripts,None

  def GetSubjobsInfo(self):
    '''Should return two lists, subjobids and subjobfns. In this case only one
    job and one file.
    '''
    return [0], [[self.output_fn]]


def CombineMultipleOutputSephFiles(batch_task_executor, local_seph_list, output_fn, combine_pars="", datapath=None, initial_seph_domain_file=None):
  '''Use this function to stack multiple .H sep files into a single one. This is useful in cases like stacking all partial images to one single final
     image in a migration task.
  '''
  bte = batch_task_executor
  param_reader = batch_task_executor.job_param_reader
  ctc = CombineTaskComposer(param_reader, local_seph_list, abspath(output_fn),
      combine_pars, datapath, initial_seph_domain_file)
  prefix = param_reader.prefix
  bte.LaunchBatchTask(prefix, ctc)
  return

