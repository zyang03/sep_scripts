#!/usr/bin/python
import commands,os,sys
import pbs_util
import sepbase
import unittest
import pickle as pickle

## Test if the pickle module can be used in checkpointing the wei-inversion.

class WeiInversionBookkeeper(Object):
  # For resume_stage, different stages during the resume of program.
  IMG_CALC = 0
  DIMG_CALC = 1
  GRAD_CALC = 2
  SRCH_CALC = 3
  VEL12_CALC = 4
  IMG1_CALC = 5
  OBJ1_CALC = 6
  IMG2_CALC = 7
  OBJ2_CALC = 8
  VELNEW_CALC = 9

  def __init__(stepsizes_list, objfuncs, save_filename):
    '''This class is used for Bookkeeping the inversion history/status, so that it can be resumed later on.
    Args:
      Stepsizes: A list of stepsizes recorded for the inversion hisotry.
      objfuncs: A list recording the history of objfuncs.
      save_filename: The name of file that this class will be saved into.
    Members:
      smooth_rect_list is a list of [rect1,rect2,rect3] list that records the smoothing parameter history.
    '''
    self.stepsizes = stepsizes_list
    self.objfuncs = objfuncs
    self.save_filename = save_filename
    self.smooth_rects_list = []
    self.iter = 0
    self.solver_par = None
    self.fn_prefix = None
    self.resume_stage = None


class TestWeiInversionBookkeeper(unittest.TestCase):

  def testLoad(self):
    f = tempfile.NamedTemporaryFile()
    f.flush()
    fn = f.name
    wei_keeper = pickle.load(f)
    print wei_keeper
    print wei_keeper.__class__.__name__
    
    # Instantiate a real WeiInversionBookkeeper object and test its load/save.
    alphas = [1.,2.]
    objfuncs = [192.0,234.0,
    wei_keeper2 = 
    f.seek(0)
    pickle.dump(wei_keeper2,f)
    print wei_keeper2
???
