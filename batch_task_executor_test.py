#!/usr/bin/python

import copy
import random
import sepbase
import tempfile
import unittest

from batch_task_executor import *
import pbs_util

### An example to define a batch task through inheriting the BatchTaskComposer Task.
### Read ~zyang03/script/batch_task_executor.py to learn the detailed specifications/explanations of the interfaces defined in BatchTaskComposer.
class DummyBatchTaskComposer(BatchTaskComposer):
  def __init__(self, param_reader, njobs, avg_nfiles_perjob):
    BatchTaskComposer.__init__(self)
    self.njobs = njobs
    self.avg_nfiles_perjob = avg_nfiles_perjob
    # Create all subjobs info
    self.subjobids = range(0, self.njobs)
    self.subjobfns_list = [None]*self.njobs
    path_out = param_reader.path_out
    random.seed(0)
    # Create a random number of files for each subjob.
    for i in range(0,self.njobs):
      nfiles = random.randint(1,2*self.avg_nfiles_perjob-1)
      self.subjobfns_list[i] = [None]*nfiles
      for j in range(0,nfiles):
        self.subjobfns_list[i][j] = '%s/testfile-%s-%s.tmp' % (path_out,i,j)
    return

  def GetSubjobScripts(self, subjobid):
    '''Return the scripts content for that subjob.'''
    subjobfns = self.subjobfns_list[subjobid]
    # Build scripts that create the files designated in subjobfns
    # Simulate 40% chance a job would fail by not having full outputs.
    random.seed()
    fail = random.randint(1,100) >= 60
    scripts = []
    cnt = 0
    nf = len(subjobfns)
    nf_act = nf
    if not fail:  # Create all necessary files
      pass
    else:  # Don't generate all files
      print 'WARN: subjobid=%d will fail.' % subjobid
      if nf == 1:
        nf_act = 0
      else:
        nf_act = random.randint(1,nf-1)
    for fn in subjobfns:
      cnt += 1
      if cnt > nf_act: break
      cmd = 'Cp %s %s out=stdout \nsleep %d\n' %  ('/data/sep/zyang03/proj/batch_task/test2.H', fn, cnt)
      scripts.append(cmd)
    return scripts, str(subjobid)

  def GetSubjobsInfo(self):
    '''Should return two lists, subjobids and subjobfns.'''
    return copy.deepcopy(self.subjobids), copy.deepcopy(self.subjobfns_list)


if __name__ == '__main__':
  print "Run BatchTaskExecutor_test with params:", sys.argv
  eq_args_from_cmdline,args = sepbase.parse_args(sys.argv)
  #dict_args = sepbase.RetrieveAllEqArgs(eq_args_from_cmdline)
  param_reader = pbs_util.JobParamReader(eq_args_from_cmdline)
  dummy_btc = DummyBatchTaskComposer(param_reader,3,3)
  bte = BatchTaskExecutor(param_reader)
  prefix = param_reader.prefix
  bte.LaunchBatchTask(prefix, dummy_btc)

  # Combine the files to one single file.
  _, fns_list = dummy_btc.GetSubjobsInfo()
  fn_seph_list = [fn for fns in fns_list for fn in fns]
  print "fn_seph_list=%s" % fn_seph_list
  CombineMultipleOutputSephFiles(bte, fn_seph_list, "test-all.H")

