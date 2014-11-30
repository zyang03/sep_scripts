import random
import sepbase
import tempfile
import unittest
from pbs_util import *

def _GenSampleScript(fn_script, cmd):
  '''Generate a sample script given the script's filename).'''
  f = open(fn_script,'w')
  script_txt = """
#!/bin/tcsh
#PBS -N test
#PBS -l nodes=1:ppn=8
#PBS -q default
#PBS -V
#PBS -m e
#PBS -W x="PARTITION:sw121"
#PBS -j oe
#PBS -e /data/sep/zyang03/tmp
#PBS -o /data/sep/zyang03/tmp
#PBS -d /data/sep/zyang03/tmp
%s
  """ % (cmd)
  f.write(script_txt)
  f.close()
  return fn_script


class TestPbsSubmitter(unittest.TestCase):
  def testOnejobSubmit(self):
    queues_info = [('default',2)]
    pbs_submitter = PbsSubmitter(queues_info)  # Pending jobs cap. 
    # pbs_submitter = PbsSubmitter(queues_info, total_jobs_cap=2)  # total
    # running jobs cap
    for i in range(0,10):
      nsec = random.randint(2,8)
      cmd = 'echo for ijob=%d, sleep %d secs.\nsleep %d' % (i, nsec,nsec)
      sample_script = _GenSampleScript('/tmp/%d.sh'%i, cmd)
      pbs_submitter.SubmitJob(sample_script)
    return



_DUMMY_CMDLINE_ARGS = 'pbs_template=pbs_script_tmpl.sh path_out=path_out prefix=hess-waz3d queue=q35 csou=csou-waz3d.H vel=vel.H '

class TestGenShotsList(unittest.TestCase):

  def testRegularShotsIndexSpacing(self):
    cmd_line_args_mimic = _DUMMY_CMDLINE_ARGS+' ish_beg=0 nfiles=50 nfiles_perjob=10 '
    dict_args, _ = sepbase.parse_args(cmd_line_args_mimic.split())
    param_reader = JobParamReader(dict_args)
    ishot_list, nshots_list = GenShotsList(param_reader)
    self.assertEqual([0,10,20,30,40], ishot_list)
    self.assertEqual([10,10,10,10,10], nshots_list)

    # Try a non-zero ish_beg
    cmd_line_args_mimic = _DUMMY_CMDLINE_ARGS+' ish_beg=5 nfiles=50 nfiles_perjob=10 '
    dict_args, _ = sepbase.parse_args(cmd_line_args_mimic.split())
    param_reader = JobParamReader(dict_args)
    ishot_list, nshots_list = GenShotsList(param_reader)
    self.assertEqual([5,15,25,35,45], ishot_list)
    self.assertEqual([10,10,10,10,5], nshots_list)

    # Try a non-zero ish_beg and a shot_n1bnd
    cmd_line_args_mimic = _DUMMY_CMDLINE_ARGS+' ish_beg=5 nfiles=50 nfiles_perjob=10 shot_n1_bnd=10'
    dict_args, _ = sepbase.parse_args(cmd_line_args_mimic.split())
    param_reader = JobParamReader(dict_args)
    ishot_list, nshots_list = GenShotsList(param_reader)
    self.assertEqual([5,10,20,30,40], ishot_list)
    self.assertEqual([5,10,10,10,10], nshots_list)
    
    cmd_line_args_mimic = _DUMMY_CMDLINE_ARGS+' ish_beg=5 nfiles=50 nfiles_perjob=10 shot_n1_bnd=9'
    dict_args, _ = sepbase.parse_args(cmd_line_args_mimic.split())
    param_reader = JobParamReader(dict_args)
    ishot_list, nshots_list = GenShotsList(param_reader)
    self.assertEqual([5,9,18,27,36,45], ishot_list)
    self.assertEqual([4,9,9,9,9,5], nshots_list)

    cmd_line_args_mimic = _DUMMY_CMDLINE_ARGS+' ish_beg=5 nfiles=50 nfiles_perjob=10 shot_n1_bnd=19'
    dict_args, _ = sepbase.parse_args(cmd_line_args_mimic.split())
    param_reader = JobParamReader(dict_args)
    ishot_list, nshots_list = GenShotsList(param_reader)
    self.assertEqual([5,15,19,29,38,48], ishot_list)
    self.assertEqual([10,4,10,9,10,2], nshots_list)
    return

  def testIrregularShotsIndexSpacing(self):
    f = tempfile.NamedTemporaryFile()
    ishot_list = [2, 5, 7, 11, 23, 40]
    f.write('\n'.join(map(str,ishot_list)))
    f.flush()
    cmd_line_args_mimic = _DUMMY_CMDLINE_ARGS+' ish_beglist=%s nfiles=100 nfiles_perjob=0 ' % f.name
    dict_args, _ = sepbase.parse_args(cmd_line_args_mimic.split())
    param_reader = JobParamReader(dict_args)
    ishot_listn, nshots_list = GenShotsList(param_reader)
    print ishot_listn, nshots_list
    self.assertEqual(ishot_list, ishot_listn)
    self.assertEqual([1]*len(ishot_list), nshots_list)


if __name__ == '__main__':
  unittest.main()

