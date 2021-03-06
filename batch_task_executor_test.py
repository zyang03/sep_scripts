#!/usr/bin/python
import copy
import random
import os
import sepbase
import tempfile
import time
import unittest

from batch_task_executor import *
import pbs_util

### An example to define a batch task through inheriting the BatchTaskComposer class.
### IMPORTANT: Read /home/zyang03/script/batch_task_executor.py to learn the detailed specifications/explanations of the interfaces defined in BatchTaskComposer.

class DummyBatchTaskComposer(BatchTaskComposer):
  def __init__(self, param_reader, njobs, avg_nfiles_perjob):
    BatchTaskComposer.__init__(self)
    self.njobs = njobs
    self.avg_nfiles_perjob = avg_nfiles_perjob
    # Create all subjobs info
    self.subjobids = range(0, self.njobs)
    self.subjobfns_list = [None]*self.njobs
    path_out = param_reader.path_out
    random.seed(time.time())
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
    fail = random.randint(1,100) >= 60
    scripts = []
    cnt = 0
    nf = len(subjobfns)
    nf_act = nf
    src_fn = os.path.abspath('test2.H')
    if not fail:  # Create all necessary files
      pass
    else:  # Don't generate all files
      if nf == 1:
        nf_act = 0
      else:
        nf_act = random.randint(1,nf-1)
      print 'WARN: subjobid=%d will fail. %d/%d' % (subjobid, nf_act, nf)
    for fn in subjobfns:
      cnt += 1
      if cnt > nf_act: break
      cmd = 'Cp %s %s out=stdout \nsleep %d\n' %  (src_fn, fn, cnt)
      scripts.append(cmd)
    return scripts, str(subjobid)

  def GetSubjobsInfo(self):
    '''Should return two lists, subjobids and subjobfns.'''
    return copy.deepcopy(self.subjobids), copy.deepcopy(self.subjobfns_list)


if __name__ == '__main__':
  print "Run BatchTaskExecutor_test with params:", sys.argv
  # Check basic environment variable setup.
  assert 'SEP' in os.environ, '!Environment var SEP is not set yet, should have your seplib enviroment set up first! Check paths like /opt/SEP/'
  assert 'RSF' in os.environ, '!Environment var RSF is not set yet, should have your RSF environment set up first! Check paths like /opt/RSF'
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
  
  # Check the final result
  stat,out = commands.getstatusoutput('Attr < test-all.H param=1 | Get parform=n totsamp ')
  assert stat==0 and int(out)==4, 'Test NOT successful, final output test-all.H is not valid!'
  print 'Test Successful!'
  
