import unittest
import sepbase
import pbs_util

import batch_bornmod_script_nompi

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


_CMDLINE_ARGS = 'pbs_template=non_pbs_tmpl.sh path_out=/data/sep/zyang03/tmp prefix=test queue=q35 csou=csou-waz3d.H vel=vel.H bimgh=bimgh.H'

class TestBatchBornmodScriptNompi(unittest.TestCase):
  def testOnejobSubmit(self):
    cmd_line_args_mimic = _CMDLINE_ARGS + ' param=waz3d.param ish_beg=5 nfiles=8 nfiles_perjob=3 source_type=point '
    batch_bornmod_script_nompi.Run(['dummy']+cmd_line_args_mimic.split())
    return


if __name__ == '__main__':
  unittest.main()

