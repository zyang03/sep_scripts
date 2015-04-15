import commands,os
import pickle
import sepbase
import time
from os.path import abspath
from sepbase import line_no

def CheckPrevCmdResultCShellScript(prev_cmd):
  '''Return a piece of script that checks the return status of the previous cmd executed in the same script.'''
  cmd = '''
if ( $status != 0 ) then
  echo ! The prev cmd failed: \" %s \"
  exit -1
endif
''' % (prev_cmd)
  return cmd

def CheckSephFileError(fn_seph, check_binary=False):
  '''Check whether a .H file is a valid one, i.e. has 100% of data and has no NaN(not a number) in it.
  Args:
    fn_seph: The name of the file to be checked.
    check_binary: if False, then only check the existence and size; if True, then check in addition whether there is nan.
  Returns:
    0 if the file is OK. 1 if it has Nan; -1 if there is problem with the file itself, like not exist or binary is incomplete.
  '''
  if not check_binary:  # Use In3d command to check.
    cmd1 = "In3d %s " % fn_seph
    stat1,out1=commands.getstatusoutput(cmd1)
    if stat1 != 0:  # File content is not complete or not file not exist
      return -1
    # Search for indications of binary portion being complete.
    pos = out1.find('[  100./')
    if pos == -1:
      return -1
    else:
      return 0
  else:  # Use Attr to check the values of the binary part as well.
    cmd1 = "Attr < %s " % fn_seph
    stat1,out1=commands.getstatusoutput(cmd1)
    if stat1 != 0:  # File content is not complete.
      return -1
    nan_pos = out1.find('nan')
    if nan_pos == -1:  # not find not-a-number, file content is valid.
      return 0
    else:
      return 1

def GenShotsList(param_reader):
  '''Figure out the indices for the shots we need to run/compute.
  Return (ishot_list, nshot_list), the first shot index in each job, and the number of shots in each job.'''
  dict_args = param_reader.dict_args
  input_is_file_list = "ish_beglist" in dict_args
  if not input_is_file_list:
    # Use ish_beg, the shots are generated as an arithmetic sequence.
    assert "ish_beg" in dict_args, (
        "!Need to supply one of the two: ish_beg or ish_beglist!")
  else:
    assert "ish_beg" not in dict_args, (
        "!!! cannot have both: ish_beg & ish_beglist!")
  N = param_reader.nfiles
  n = param_reader.nfiles_perjob
  # If shots are grouped by shot_n1 amount, which means when dividing the shots for each job, don't cross the shot_n1 boundary
  shot_n1_bnd = dict_args.get("shot_n1_bnd")
  if shot_n1_bnd:  shot_n1_bnd = int(shot_n1_bnd)
  ish_start = 0; ishot_list = []; nshot_list = []
  if not input_is_file_list:
    ish_start = int(dict_args["ish_beg"])
    if not shot_n1_bnd:
      ishot_list = range(ish_start,N,n)
      nshot_list = [n]*(len(ishot_list)-1)
      nshot_list.append(N - ishot_list[-1])
    else: # divide the job such that it did not cross the given n1 boundary
      nearest_shot_n1_mult = (ish_start / shot_n1_bnd + 1) * shot_n1_bnd
      shot_end_1st_row = min(nearest_shot_n1_mult,N)
      ishot_list = range(ish_start, shot_end_1st_row, n)
      nshot_list = [n]*(len(ishot_list)-1)
      nshot_list.append(shot_end_1st_row - ishot_list[-1])
      for ii in range(nearest_shot_n1_mult, N, shot_n1_bnd):
        shot_end = min(N, ii+shot_n1_bnd)
        for ishot in range(ii,shot_end,n):
          ishot_list.append(ishot)
          nshot_list.append(min(shot_end-ishot,n))
  else:  # The input shots are listed in a file and might not be consecutive.
    file_ish_flist = dict_args["ish_beglist"]
    # read the list files to generate a list of shots
    fp_list = open(file_ish_flist,'r')
    while True:
      line = fp_list.readline();
      if not line:
        break
      else:  # Read in the number stored in this line into a number.
        line = line.strip()
        if line:
          ishot_list.append(int(line))
          nshot_list.append(1)  # Assume in this case, each job only does one shot.
    fp_list.close()
    ish_start = ishot_list[0]

  njobs_max = param_reader.njobs_max
  print "ish_start=%d:  njobs_max=%d" % (ish_start, njobs_max)
  if njobs_max < len(ishot_list):  del ishot_list[njobs_max:]
  return ishot_list, nshot_list


class ShotsInfo:
  def __init__(self, fn_shots_info):
    '''Helper class that manages the individual shot file information stored in a .shotsInfo file.'''
    self._fn_shots_info = fn_shots_info
    # Read all the lines.
    fp = open(fn_shots_info,'r')
    self.lines = []
    for line in fp:
      line = line.strip()
      if line:
        self.lines.append(line)
    fp.close()

  def TotNumShots(self):
    return len(self.lines)-2

  def ShotFileNameAt(self,ish):
    '''Find the filename in the shotInfoFile corresponding to the shot index.
    ####and extract the receiver geometry.'''
    return self.lines[ish+2].split(" ")[0]  # Extract the first word, which is the filename.

  def ShotFileApertureAt(self, ish):
    '''Return a tuple of [xmin,xmax,ymin,ymax] indicating the aperture of the shot record.'''
    return map(float, self.lines[ish+2].split(" ")[1:])


class JobParamReader:
  '''Parse the common parameters for PBS jobs.'''
  def __init__(self, dict_args):
    self.dict_args = dict_args
    self.fname_template_script = dict_args['pbs_template']
    self.queues = dict_args.get('queues','default').split(',')
    self.queues_cap = dict_args.get('queues_cap')
    nqueue = len(self.queues)
    if self.queues_cap:  # Not None
      self.queues_cap = map(int, self.queues_cap.split(','))
      assert len(self.queues_cap) == nqueue, 'queues and queues_cap have different num_of_elements!'
    else:  # Provide default values.
      self.queues_cap = [15]*nqueue
    self.prefix = dict_args['prefix']  # The prefix used for generating filenames for intermediate/output datafiles.
    # The cap of total number of jobs in *each* queue at any given time.
    self.total_jobs_cap = dict_args.get('total_jobs_cap')
    if self.total_jobs_cap is not None:
      self.total_jobs_cap = map(int, self.total_jobs_cap.split(','))
      assert nqueue == len(self.total_jobs_cap)
    self.njobs_max = 1  # For now set it to 1.
    self.path_out = abspath(dict_args.get("path_out", os.getcwd()))
    self.path_tmp = abspath(dict_args.get('path_tmp', '/tmp'))
    return

class ParallelParamReader(JobParamReader):
  '''A subclass that read extra parameters about job parallelization, mostly through sharding the input data.'''
  def __init__(self, dict_args):
    JobParamReader.__init__(self, dict_args)
    self.nfiles = int(dict_args['nfiles'])  # Total number of shots to simulate/generate/compute.
    self.nfiles_perjob = int(dict_args.get("nfiles_perjob", 1))
    assert dict_args.get("nfiles_perbatch") is None, 'Obsolete option nfiles_perbatch!!'
    self.njobs_max = int(dict_args.get('njobs_max', self.nfiles))  # Total number of jobs to simulate, will stop submission after such number of jobs have been submitted.
    
class WeiParamReader(ParallelParamReader):
  def __init__(self, dict_args):
    ParallelParamReader.__init__(self, dict_args)  # Call base class constructor.
    # Get the velocity file, csou file and filename prefix for intermediate files.
    self.source_type = dict_args.get("source_type", "plane")
    self.fn_csou = abspath(dict_args["csou"])
    self.fn_v3d = abspath(dict_args["vel"])
    # If user only select a portion of frequencies to migrate/compute/model, w_f,w_n
    self.ws_wnd_f = self.ws_wnd_n = self.ws_wnd_d = None

    if 'ws_wnd' in self.dict_args:  # ws_wnd=f,n[,d]
      str_list = self.dict_args["ws_wnd"].split(",")
      wnd_fnd = map(int, (self.dict_args["ws_wnd"].split(",")))
      self.ws_wnd_f = wnd_fnd[0]; self.ws_wnd_n = wnd_fnd[1]
      self.ws_wnd_d = 1
      if len(wnd_fnd) >= 3:
        self.ws_wnd_d = wnd_fnd[2]
    # Get global domain for imaging or Hessian computation.
    self.g_output_image_domain = [None]*6  # [xmin,xmax,ymin,ymax,zmin,zmax]
    if 'xs' in dict_args:
      strs_minmax = dict_args["xs"].split(",")
      self.g_output_image_domain[0:2] = map(float, strs_minmax)
    if 'ys' in dict_args:
      strs_minmax = dict_args["ys"].split(",")
      self.g_output_image_domain[2:4] = map(float, strs_minmax)
    if 'zs' in dict_args:
      strs_minmax = dict_args["zs"].split(",")
      self.g_output_image_domain[4:6] = map(float, strs_minmax)
    print "global_output_domain_xs,ys,zs = ", self.g_output_image_domain


class PbsScriptCreator:
  """Given the input arg parameters, generate a PBS script body."""
  def __init__(self, param_reader):
    self.param_reader = param_reader
    self.dict_args = param_reader.dict_args
    self.user = self.dict_args['user']
    self._starting_new_script = False
    self._job_filename_stem = None

  def AppendScriptsContent(self, scripts):
    '''Append the list of lines in 'scripts' to the underlying script file.
    Returns the script file name.'''
    prefix = self.param_reader.prefix
    if self._starting_new_script:  # Create the new script
      self._starting_new_script = False
      fname_template_script = self.param_reader.fname_template_script
      cmd1 = "cp %s %s" % (fname_template_script, self.fn_script)
      sepbase.RunShellCmd(cmd1)
      nnodes = int(self.dict_args.get('nnodes',1))  # By default, use one node per job
      if nnodes != 0:  # Need to change the number of nodes used for this job
        cmd1 = ("sed -i 's/#PBS\ -l\ nodes=1/#PBS\ -l\ nodes=%d/g'   %s" %
                (nnodes, self.fn_script))
        sepbase.RunShellCmd(cmd1)
      # Change jobname for better readability.
      cmd0 = "sed -i '/#PBS -N/c\#PBS -N %s-%s' %s" % (
          prefix, self._job_filename_stem, self.fn_script)
      # Redirect PBS output, change the entire PBS -o and -e line
      cmd1 = "sed -i '/#PBS -o/c\#PBS -o %s' %s" % (
          self.fn_log, self.fn_script)
      cmd2 = "sed -i '/#PBS -e/c\#PBS -e %s' %s" % (
          self.fn_log, self.fn_script)
      # Change the working directory to the output directory
      cmd2 += "\nsed -i '/#PBS -d/c\#PBS -d %s' %s" % (
          self.param_reader.path_out, self.fn_script)
      sepbase.RunShellCmd(cmd0+'\n'+cmd1+'\n'+cmd2)
    # Then write the content in scripts.
    fp_o = open(self.fn_script,'a'); fp_o.writelines(scripts); fp_o.close()
    return self.fn_script

  def CmdFinalCleanUpTempDir(self):
    cmd = '\n# Final clean up, remove the files at tmp folder.'
    cmd += "\nfind %s/ -maxdepth 1 -type f -user %s -exec rm {} \\;\n" % (
        self.param_reader.path_tmp, self.user)
    return cmd

  def CreateScriptForNewJob(self, script_filename_stem):
    """Construct the pbs script from script_template.
    The actual script file write happens when you call the first AppendScriptsContent() after calling this funciton.
    Args:
      script_filename_stem: The basename (without extension) for the new script name.
      """
    self._starting_new_script = True
    self._job_filename_stem = script_filename_stem
    path_out = self.param_reader.path_out
    prefix = self.param_reader.prefix
    self.fn_script = '%s/%s-%s.sh' % (path_out, prefix, script_filename_stem)
    self.fn_log = '%s/%s-%s.log' % (path_out, prefix, script_filename_stem)
    return

  def CmdCombineMultipleOutputSephFiles(self, local_seph_list, output_fn, combine_pars="", datapath=None, initial_seph_domain_file=None):
    '''
    Args:
      initial_seph_domain_file: The sep header file used for determine the output size, if == None then use the first element in local_seph_list.
    '''
    if datapath is None:
      datapath = os.path.split(os.path.abspath(output_fn))[0]
    cmd = '# Combine the results from multiple shots into one.\n'
    n = len(local_seph_list)
    if n == 1:
      cmd1 = "time Cp %s %s datapath=%s/" % (local_seph_list[0],output_fn,datapath)
    else:
      if initial_seph_domain_file is None:
        initial_seph_domain_file = local_seph_list[0]
      #axis 3,4,5 are (x,y,z)
      if n <= 6:  # If the list is small, just pile filenames on the command line arguments.
        cmd1 = "time %s/Combine <%s fnames=%s output=%s %s datapath=%s/" % (
            self.dict_args['YANG_BIN'],initial_seph_domain_file,
            ','.join(local_seph_list), output_fn, combine_pars,datapath)
      else:  # Write filenames line-by-line into a temporary file.
        fn_tflist = "%s.flist"%(os.path.splitext(output_fn)[0])
        fp_tflist = open(fn_tflist,"w")
        fp_tflist.write("\n".join(local_seph_list))
        fp_tflist.close()
        #axis 3,4,5 are (x,y,z)
        cmd1 = "time %s/Combine <%s filelist=%s output=%s %s datapath=%s/" % (
            self.dict_args['YANG_BIN'],initial_seph_domain_file,
            fn_tflist, output_fn, combine_pars, datapath)
    # The combine process could go wrong, therefore add a conditional clause
    cmd += (cmd1+CheckPrevCmdResultCShellScript(cmd1))
    return cmd


class WeiScriptor:
  '''Given the input arg parameters, generate scripts that performs a WEI (Wave equation inversion) operation.'''
  def __init__(self, param_reader):
    self.param_reader = param_reader
    self.dict_args = param_reader.dict_args
    self.sz_shotrange = None

  def NewJob(self, sz_shotrange):
    """Call this func first everytime you start a new job."""
    self.sz_shotrange = sz_shotrange
    path_out = self.param_reader.path_out
    prefix = self.param_reader.prefix
    self.fnt_output_list = []
    return

  def CmdWetomoPerShot(self, ish, image_domains = (None,)*6):
    '''Generate shell cmd for doing the image-space tomo operator: dimg ==> dvel.
    image_domains: is a tuple of (xmin,xmax,ymin,ymax,zmin,zmax) that indicate the imaging domain.'''
    cmd = '# Perform Wetomo adj for the current shot.\n'
    path_tmp = self.param_reader.path_tmp
    prefix = self.param_reader.prefix
    self.fnt_output = '%s/dvel-%s-%04d.H' % (path_tmp,prefix,ish)
    self.fnt_output_list.append(self.fnt_output)
    cmd1 = "time %s/bwi-wet3d-Zh.x %s mode=tomadj crec=%s csou=%s dimg=%s bvel=%s dvel=%s datapath=%s/" % (
        self.dict_args['TANG_BIN'], self.dict_args['MIG_PAR_WAZ3D'], self.fnt_crec, self.fnt_csou, self.fnt_dimg,self.fnt_bvel,self.fnt_output, path_tmp)
    # The output dimension will always be the same as the input vel model.
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdWetomoimitPerShot(self, ish, image_domains = (None,)*6):
    '''Generate shell cmd for doing the image-space tomoimit operator: dimg,bimgh0 ==> dvel.
    image_domains: is a tuple of (xmin,xmax,ymin,ymax,zmin,zmax) that indicate the imaging domain.'''
    cmd = '# Perform Wetomo adj for the current shot.\n'
    path_tmp = self.param_reader.path_tmp
    prefix = self.param_reader.prefix
    self.fnt_output = '%s/dvel-%s-%04d.H' % (path_tmp,prefix,ish)
    self.fnt_output_list.append(self.fnt_output)
    wem_bin_path = self.dict_args['TANG_BIN']
    final_cmd = cmd
    if True:  # Do the cost-saving way
      cmd1 = "time %s/bwi-wet3d-Zh.x %s mode=tomimit csou=%s dimg=%s bimgh0=%s bvel=%s dvel=%s datapath=%s/" % (
          wem_bin_path,self.dict_args['MIG_PAR_WAZ3D'], self.fnt_csou,self.fnt_dimg,self.fnt_bimgh0,self.fnt_bvel,self.fnt_output, path_tmp)
    # The output dimension will always be the same as the input vel model.
      final_cmd += cmd1+CheckPrevCmdResultCShellScript(cmd1)
    else :  # Do the more expensive way
      self.fnt_h0_crec = '%s/crec-h0-%04d.H' % (path_tmp,ish)
      cmd1 = "time %s/bwi-wem3d-Zh.x %s %s mode=imgfwd crec=%s csou=%s bimg=%s bvel=%s datapath=%s/" % (
          wem_bin_path, self.dict_args['MIG_PAR_WAZ3D'], self.dict_args['GEOM_GXY'], self.fnt_h0_crec, self.fnt_csou, self.fnt_bimgh0,self.fnt_bvel, path_tmp)
      final_cmd += cmd1+CheckPrevCmdResultCShellScript(cmd1)
      cmd2 = "time %s/bwi-wet3d-Zh.x %s mode=tomadj csou=%s dimg=%s crec=%s bvel=%s dvel=%s datapath=%s/" % (
          wem_bin_path,self.dict_args['MIG_PAR_WAZ3D'], self.fnt_csou,self.fnt_dimg,self.fnt_h0_crec,self.fnt_bvel,self.fnt_output, path_tmp)
      final_cmd += cmd2+CheckPrevCmdResultCShellScript(cmd2)
    return final_cmd

  def CmdMigrationPerShot(self, ish, image_domains = (None,)*6):
    '''Generate shell cmd for doing the migration.
    image_domains: is a tuple of (xmin,xmax,ymin,ymax,zmin,zmax) that indicate the imaging domain.'''
    cmd = '# Perform migration for the current shot.\n'
    path_tmp = self.param_reader.path_tmp
    prefix = self.param_reader.prefix
    self.fnt_imgh = '%s/imgh-%s-%04d.H' % (path_tmp,prefix,ish)
    self.fnt_output_list.append(self.fnt_imgh)
    cmd1 = "time %s/bwi-wem3d-Zh.x %s %s %s mode=imgadj crec=%s csou=%s bimg=%s bvel=%s datapath=%s/ " % (
        self.dict_args['TANG_BIN'], self.dict_args['MIG_PAR_WAZ3D'], self.dict_args.get('IMG_PAR',""),self.dict_args['SS_OFFSET_PAR'], self.fnt_crec, self.fnt_csou, self.fnt_imgh,self.fnt_bvel, path_tmp)
    xmin, xmax = image_domains[0:2]
    ymin, ymax = image_domains[2:4]
    zmin, zmax = image_domains[4:6]
    if xmin is not None:
      cmd1 += " image_xmin=%.1f image_xmax=%.1f image_ymin=%.1f image_ymax=%.1f " % (
          xmin,xmax,ymin,ymax)
    if zmin is not None:
      cmd1 += " image_zmin=%.1f image_zmax=%.1f " % (zmin,zmax)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdBornModelingPerShot(self, ish):
    cmd = '# Do born modeling for the current shot.\n' 
    path_tmp = self.param_reader.path_tmp
    src_type = self.param_reader.source_type
    self.fnt_crec = '%s/crec-model-%04d.H' % (path_tmp,ish)
    wem_bin_path = self.dict_args['TANG_BIN']
    if src_type == 'plane':
      cmd1 = "time %s/bwi-wem3d-Zh.x %s %s mode=imgfwd crec=%s csou=%s bimg=%s bvel=%s datapath=%s/" % (
          wem_bin_path, self.dict_args['MIG_PAR_WAZ3D'], self.dict_args['GEOM_GXY'], self.fnt_crec, self.fnt_csou, self.fnt_bimg,self.fnt_bvel, path_tmp)
    else:
      cmd1 = "time %s/bwi-wem3d-Zh.x %s %s mode=imgfwd crec=%s csou=%s bimg=%s bvel=%s datapath=%s/" % (
          wem_bin_path, self.dict_args['MIG_PAR_WAZ3D'], self.dict_args['GEOM_GXY'], self.fnt_crec, self.fnt_csou, self.fnt_bimg,self.fnt_bvel, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpbvelForEachJob(self, zmax=None):  # Notice we can not change zmin, because the wfld has to propagate from the very top of model.
    cmd = '# Copy the background vel model file to local disk.\n'
    fn_v3d = self.param_reader.fn_v3d
    path_tmp = self.param_reader.path_tmp
    self.fnt_bvel = '%s/vel-%s.H' % (path_tmp,self.sz_shotrange)
    if zmax is None:
      cmd1 = "time Cp %s %s out=%s@ " % (fn_v3d, self.fnt_bvel, self.fnt_bvel)
    else:
      cmd1 = "time %s/YWindow3d max3=%g <%s >%s out=%s@ " % (self.dict_args['YANG_BIN'], zmax, fn_v3d, self.fnt_bvel,self.fnt_bvel)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpbimgForEachJob(self):
    cmd = '# Copy the background image(reflectivity model) file to local disk.\n'
    path_tmp = self.param_reader.path_tmp
    self.fn_bimg = abspath(self.dict_args["bimg"])
    self.fnt_bimg = '%s/bimg-%s.H' % (path_tmp,self.sz_shotrange)
    # For cping base imgh to local folder.
    cmd1 = "time Cp %s %s datapath=%s/" % (self.fn_bimg,self.fnt_bimg, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)
  
  def CmdCpbimgh0ForEachJob(self):  # For tomoimit
    cmd = '# Copy the background zero-offset image file to local disk.\n'
    path_tmp = self.param_reader.path_tmp
    self.fn_bimgh0 = abspath(self.dict_args["bimgh0"])
    self.fnt_bimgh0 = '%s/bimgh0-%s.H' % (path_tmp,self.sz_shotrange)
    # For cping base imgh to local folder.
    cmd1 = "time Cp %s %s datapath=%s/" % (self.fn_bimgh0,self.fnt_bimgh0, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpdimgForEachJob(self):
    cmd = '# Copy the image perturbation file to local disk.\n'
    path_tmp = self.param_reader.path_tmp
    self.fn_dimg = abspath(self.dict_args["dimg"])
    self.fnt_dimg = '%s/dimg-%s.H' % (path_tmp,self.sz_shotrange)
    # For cping base imgh to local folder.
    cmd1 = "time Cp %s %s datapath=%s/" % (self.fn_dimg,self.fnt_dimg, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpCrecForEachShot(self, ish, fn_shot_crec):
    '''Copy the related crec binaries (e.g. data) to local folder, this applies to
    the imaging case not modeling case.'''
    cmd = '# Copy the data of current shot to local disk.\n'
    path_tmp = self.param_reader.path_tmp
    self.fnt_crec = '%s/crec-model-%04d.H' % (path_tmp,ish)
    ws_wnd_f, ws_wnd_n, ws_wnd_d = self.param_reader.ws_wnd_f, self.param_reader.ws_wnd_n, self.param_reader.ws_wnd_d
    if ws_wnd_n is not None:
      cmd1 = "Window3d <%s f3=%d n3=%d j3=%d >%s squeeze=n datapath=%s/ " % (
          fn_shot_crec, ws_wnd_f,ws_wnd_n,ws_wnd_d, self.fnt_crec, path_tmp)
    else:
      cmd1 = "Cp %s %s datapath=%s/ "% (fn_shot_crec,self.fnt_crec, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCsouForEachShot(self,ish):
    '''Generate the command for each shot.'''
    cmd = '# Generate the source file for current shot on local disk.\n'
    path_tmp = self.param_reader.path_tmp
    # If user only select a portion of frequencies to migrate/compute/model, w_f,w_n
    ws_wnd_f, ws_wnd_n, ws_wnd_d = self.param_reader.ws_wnd_f, self.param_reader.ws_wnd_n, self.param_reader.ws_wnd_d
    fn_csou = self.param_reader.fn_csou
    if self.param_reader.source_type == 'plane':
      fnt_csou = "%s/csou-plane-%04d.H" % (path_tmp, ish)  # Append the filename fn_csou with shotIndex as the new filename.
      # The source func for each shot is different. Needs to do Window based on it.
      n4 = int(sepbase.get_sep_axis_params(fn_csou,4)[0])
      f5 = ish / n4
      f4 = ish % n4
      if ws_wnd_n is not None:
        cmd2 = "Window3d <%s f3=%d n3=%d j3=%d n4=1 n5=1 f4=%d f5=%d >%s squeeze=n datapath=%s/ " % (
            fn_csou,ws_wnd_f,ws_wnd_n,ws_wnd_d, f4,f5,fnt_csou,path_tmp)
      else:
        cmd2 = "Window3d <%s n4=1 n5=1 f4=%d f5=%d >%s squeeze=n datapath=%s/ "%(fn_csou,f4,f5,fnt_csou,path_tmp)
    else:  # Point Source
      fnt_csou = "%s/csou-pt-%04d.H" % (path_tmp, ish)  # Append the filename fn_csou with shotIndex as the new filename.
      if ws_wnd_n is not None:
        cmd2 = "Window3d <%s f3=%d n3=%d j3=%d >%s squeeze=n datapath=%s/ " % (
            fn_csou,ws_wnd_f,ws_wnd_n,ws_wnd_d, fnt_csou,path_tmp)
      else:
        cmd2 = "Cp %s %s datapath=%s/ "%(fn_csou, fnt_csou, path_tmp)
    self.fnt_csou = fnt_csou
    return cmd+cmd2+CheckPrevCmdResultCShellScript(cmd2)


class PbsSubmitter:
  """Implements a greedy job submission strategy."""
  def __init__(self, queues_info=[('default',1)], total_jobs_cap=None, user=None):
    """
    Args:
      queues_info: A list of queue names, ordered by the priorities(descending). 
          Each tuple has two fields, [0] is the name of queue and [1] is the
          max_num_Q_jobs, i.e. maximum number of jobs pending in that queue
          (waiting for execution). In a normal scenario, the last queue should
          be 'default'.
      total_jobs_cap: The cap for running jobs + pending jobs for EACH queue, (for the sake of code simplicity, this is a per-queue cap).
    """
    nq = len(queues_info)
    assert nq > 0
    self._queues_info = queues_info[:]
    if user is None:
      self._user_name = os.environ['USER']
    else:
      self._user_name = user
    if total_jobs_cap is None:
      self._total_jobs_cap = [60]*nq  # Can have at most 60 jobs on the cluster.
    else:
      assert nq == len(total_jobs_cap)
      self._total_jobs_cap = total_jobs_cap[:]

  def WaitOnAllJobsFinish(self, grep_pattern = None):
    '''The function will block our script until all related jobs (that can be found under the current user and matches the grep_pattern) have been finished.
    Args:
      grep_pattern: An optional pattern string that will be used to find all jobs under the given user and matches the grep_pattern.'''
    icnt = 0
    while True:
      # Exclude the error jobs (' C ') coz these jobs can remain in qstat info for quite some time.
      if not grep_pattern:
        cmd = "qstat -a | grep -v \' C \' | grep %s | wc -l " % (self._user_name)
        grep_pattern = ""
      else:
        # Due to the column width constrain from qstat display, only maximum of 15 chars in grep_pattern(job name basically) will be shown.
        cmd = "qstat -a | grep -v \' C \' | grep %s | grep %s | wc -l " % (self._user_name, grep_pattern[0:15])
      stat1,out1=commands.getstatusoutput(cmd)
      if int(out1) > 0:
        icnt += 1
        if icnt == 1: print "Wait On All Jobs to Finish (%s)..." % grep_pattern[0:15]
        time.sleep(5)
      else:
        break
    return

  def SubmitJob(self, fn_script):
    #Submit the job script to pbs system by looking at if there are enough running jobs
    num_queues = len(self._queues_info)
    i_queue = 0
    icnt = 0
    while True:
      queue_name, queue_cap = self._queues_info[i_queue]
      jobR = 0; jobQ = 0; jobC = 0
      # Check how many jobs are in this queue.
      cmd_template = "qstat -a | grep %s | grep \' %s \' | grep %s | wc -l " 
      cmd1 = cmd_template % (self._user_name, "R", queue_name)
      stat1,out1=commands.getstatusoutput(cmd1)
      cmd1 = cmd_template % (self._user_name, "Q", queue_name)
      stat2,out2=commands.getstatusoutput(cmd1)
      cmd1 = cmd_template % (self._user_name, "C", queue_name)
      stat3,out3=commands.getstatusoutput(cmd1)
      
      jobR = int(out1); jobQ = int(out2); jobC = int(out3)
      jobC = 0  # Just ignore error jobs at this moment.
      if icnt == 0:
        print "jobs status in the queue <%s>, R/ Q:C, %d/ %d:%d" % (queue_name, jobR, jobQ, jobC)
      njob_pending = jobQ + jobC
      njob_total = njob_pending + jobR
      if njob_pending < queue_cap and njob_total < self._total_jobs_cap[i_queue]:
        cmd1 = "qsub -q %s %s" % (queue_name, fn_script)
        print line_no(), ("submitting job %s to Queue:%s" %
                          (fn_script, queue_name))
        stat1, out1 = commands.getstatusoutput(cmd1)
        if stat1 != 0:
          sepbase.err("submit job failed, msg=%d,%s" % (stat1,out1))
        os.system("sleep 5")  # Stagger the job start-off time a bit.
        break
      else:
        # if not last queue, then try next queue
        if i_queue != num_queues-1:
          i_queue += 1
        else:  # back-off for a while before retrying
          icnt += 1
          if icnt == 1:  # Do not print multiple times of the same waiting msg
            print "Waiting on the pbs queue..."
          os.system("sleep 60")  # Sleep a while (secs) before do the query again.
          # Then start polling the first queue again.
          i_queue = 0
    return



def OverlapRectangle(rect1,rect2):
  '''Compute the overlap between two rectangles, the elements in rect2 can be empty.
  '''
  xmin_1,xmax_1,ymin_1,ymax_1 = rect1
  xmin_2,xmax_2,ymin_2,ymax_2 = rect2
  if xmin_2 is not None:
    xmin_1 = max(xmin_1,xmin_2); xmax_1 = min(xmax_1,xmax_2)
  if ymin_2 is not None:
    ymin_1 = max(ymin_1,ymin_2); ymax_1 = min(ymax_1,ymax_2)
  assert xmin_1 <= xmax_1 and ymin_1 <= ymax_1
  return [xmin_1,xmax_1,ymin_1,ymax_1]


def UnionRectangle(rect1, rect2):
  '''Compute the union of two rectangles (The smallest rectangle that can fully cover both input rects), returns also an rectangle.
  The elements in rect2 can be empty.
  '''
  xmin_1,xmax_1,ymin_1,ymax_1 = rect1
  xmin_2,xmax_2,ymin_2,ymax_2 = rect2
  if xmin_2 is not None:
    xmin_1 = min(xmin_1,xmin_2); xmax_1 = max(xmax_1,xmax_2)
  if ymin_2 is not None:
    ymin_1 = min(ymin_1,ymin_2); ymax_1 = max(ymax_1,ymax_2)
  return [xmin_1,xmax_1,ymin_1,ymax_1]

class WemvaTypeParser:
  def __init__(self, wemva_type, calc_dimg):
    '''Columns meaning:
        col 0: calc_o2a if calc_dimg==False
        col 1: calc_o2a if calc_dimg==True
        col 2: calc_a2o if calc_dimg==True
    '''
    self._map_wemva_type_calc_ang = {
        "1" : (False, False, False), # Stack Power
        "2" : (False, False, False), # Stack Power
        "3" : (True, True, False), # Stack Power
        "11": (False, True, True),  # RMO
        "12": (False, True, True),  # RMO
        "13": (True, True, True),  # RMO
        "61": (False, False,False), # DSO
        "62": (False, False,False),
        "63": (False, False,False),
        "64": (True, True,False),
    }
    if not calc_dimg:
      self.calc_ang_gather = self._map_wemva_type_calc_ang[wemva_type][0]
      self.calc_a2o = False
      if self.calc_ang_gather:  # sanity check
        assert self._map_wemva_type_calc_ang[wemva_type][1]
    else:
      self.calc_ang_gather = self._map_wemva_type_calc_ang[wemva_type][1]
      self.calc_a2o = self._map_wemva_type_calc_ang[wemva_type][2]
    # Some sanity check
    if self.calc_a2o: assert self.calc_ang_gather
    self.tomo_mode = "tomadj"
    if wemva_type in ["11","12","13"]:
      self.tomo_mode = "tomimit"
    return

class SolverParamReader:
  '''Hold all solver parameters for wei inversion.'''
  def __init__(self, dict_args):
    # Allowed parameter value range for the model space.
    self.maxval = float(dict_args['maxval'])
    self.minval = float(dict_args['minval'])
    # Smoothing parameters, for 1st, 2nd and 3rd axis. (x,y,z) in wei case.
    self.smooth_rect_sizes = map(int, dict_args['smooth_rect_sizes'].split(','))
    # smooth_rect_reductions decides how much the smoothing strengh will reduce per iteration.
    self.smooth_rect_reductions = map(int, dict_args['smooth_rect_reductions'].split(','))
    assert(len(self.smooth_rect_sizes)==3); assert(len(self.smooth_rect_reductions)==3);
    self.nrepeat = int(dict_args.get('nrepeat',1))
    # 'initial_perturb_scale' determines the starting stepsize the inversion will choose to generate trial models, i.e. the starting delta_m = initial_perturb_scale*normalized_grad. Assuming normalized_grad has a RMS of 1.0
    self.initial_perturb_scale = float(dict_args['initial_perturb_scale'])
    self.max_perturb_scale = float(dict_args['max_perturb_scale'])


class WeiInversionBookkeeper:
  # For resume_stage, different stages during the resume of program,
  # means synching right after IMG/DIMG/.../ operation.
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

  def __init__(self, stepsizes, objfuncs):
    '''This class is used for Bookkeeping the inversion history/status, so that it can be resumed later on.
    Args:
      Stepsizes: A list of stepsizes recorded for the inversion hisotry.
      objfuncs: A list recording the history of objfuncs.
      save_filename: The name of file that this class will be saved into.
    Members:
      smooth_rects_list is a list of [rect1,rect2,rect3] list that records the smoothing parameter history.
    '''
    self.stepsizes = stepsizes
    self.alpha = None
    self.objfuncs = objfuncs
    self.objfunc = None
    self.objfunc1 = None
    self.objfunc2 = None
    self.smooth_rects_history = []
    self.smooth_rects = []
    self.iter = 0
    self.fn_v = None  # Current velocity model
    self.fn_prefix = None
    self.resume_stage = None

  def __str__(self):
    '''Customize a print() method.'''
    return """stepsizes=%s\nalpha=%s\nobjfuncs=%s\nobjfunc_012=%s\nsmooth_rects_history=%s\nsmooth_rects=%s
iter=%d\nfn_v=%s\nfn_prefix=%s\nresume_stage=%s
    """ % (self.stepsizes,self.alpha,self.objfuncs,[self.objfunc,self.objfunc1,self.objfunc2],
           self.smooth_rects_history,self.smooth_rects,self.iter,self.fn_v,self.fn_prefix,self.resume_stage)

  def __eq__(self, other):
    if other.__class__.__name__ != self.__class__.__name__:
      return False
    if (self.stepsizes==other.stepsizes and
        self.objfuncs==other.objfuncs and
        self.save_filename==other.save_filename and
        self.smooth_rects_list==other.smooth_rects_list and
        self.iter==other.iter and
        self.fn_prefix==other.fn_prefix and
        self.resume_stage==other.resume_stage):
      return True
    else:
      return False

  def Save(self, resume_stage, save_filename):
    '''Save the current status into the save_filename.'''
    self.resume_stage = resume_stage
    fp = open(save_filename,'wb')
    pickle.dump(self,fp)
    fp.close()


def SplitFullFilePath(abs_file_path):
  '''Split a filename into path, name, extension (without .dot).'''
  fpath, fname = os.path.split(abs_file_path)
  fbasename, fext = os.path.splitext(fname)
  return (fpath,fbasename,fext)

