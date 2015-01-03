#!/usr/bin/python
import commands,os,sys
from pbs_util import *
import sepbase
import tempfile
import unittest
import pickle as pickle

## Test if the pickle module can be used in checkpointing the wei-inversion.

class TestWeiInversionBookkeeper(unittest.TestCase):

  def testLoad(self):
    f = tempfile.NamedTemporaryFile()
    fn = f.name
    pickle.dump(['joker',2,{'salamander':'koolaid'}],f)
    f.flush()
    f.seek(0)
    wei_keeper = pickle.load(f)
    print wei_keeper
    print wei_keeper.__class__.__name__
    
    # Instantiate a real WeiInversionBookkeeper object and test its load/save.
    alphas = [1.,2.]
    objfuncs = [192.0,234.0,248.0]
    wei_keeper2 = WeiInversionBookkeeper(alphas,objfuncs,fn)
    wei_keeper2.iter = 7
    wei_keeper2.fn_prefix = 'joke'
    wei_keeper2.resume_stage = WeiInversionBookkeeper.IMG2_CALC
    f.seek(0)
    pickle.dump(wei_keeper2,f)
    f.seek(0)
    wei_keeper_loaded = pickle.load(f)
    print wei_keeper_loaded.__class__.__name__
    print 'object we start with:',wei_keeper2
    print 'object after save/load:', wei_keeper_loaded
    self.assertEqual(wei_keeper2, wei_keeper_loaded)

if __name__ == '__main__':
  unittest.main()

