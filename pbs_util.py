import commands,os
import sepbase
import time
from os.path import abspath
from sepbase import line_no


def CheckPrevCmdResultCShellScript(prev_cmd):
  '''Return a piece of script that checks the return status of the previous cmd executed in the same script.'''
  return '''
if ( $status != 0 ) then
  echo ! The prev cmd failed: \" %s \"
  exit -1
endif
  ''' % (prev_cmd)

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
    self._fn_shots_info = fname_shots_info
    # Read all the lines.
    fp = open(fname_shots_info,'r')
    self.lines = []
    for line in fp:
      line = line.strip()
      if line:
        self.lines.append(line)
    fp.close()

  def ShotFileNameAt(ish):
    '''Find the filename in the shotInfoFile corresponding to the shot index.
    ####and extract the receiver geometry.'''
    return lines[ish+2].split(" ")[0]  # Extract the first word, which is the filename.

  def ShotFileApertureAt(ish):
    '''Return a tuple of [xmin,xmax,ymin,ymax] indicating the aperture of the shot record.'''
    return map(float, lines[ish+2].split(" ")[1:])


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
      assert len(queues_cap) == nqueue, 'queues and queues_cap have different num_of_elements!'
    else:  # Provide default values.
      self.queues_cap = [1]*nqueue
    # The cap of total number of jobs in a queue at any given time.
    self.total_jobs_cap = int(dict_args.get('total_jobs_cap',60))
    self.nfiles = int(dict_args['nfiles'])  # Total number of shots to simulate/generate/compute.
    self.nfiles_perjob = int(dict_args.get("nfiles_perjob", 1))
    assert dict_args.get("nfiles_perbatch") is None, 'Obsolete option nfiles_perbatch!!'
    self.njobs_max = int(dict_args.get('njobs_max', self.nfiles))  # Total number of jobs to simulate, will stop submission after such number of jobs have been submitted.
    self.path_out = abspath(dict_args.get("path_out", os.getcwd()))
    self.path_tmp = abspath(dict_args.get('path_tmp', '/tmp'))
    # Get the velocity file, csou file and filename prefix for intermediate files.
    self.source_type = dict_args.get("source_type", "plane")
    self.fn_csou = abspath(dict_args["csou"])
    self.fn_v3d = abspath(dict_args["vel"])
    self.prefix = dict_args['prefix']
    # If user only select a portion of frequencies to migrate/compute/model, w_f,w_n
    self.ws_wnd_f = None
    self.ws_wnd_n = None
    if 'ws_wnd' in self.dict_args:
      str_list = self.dict_args["ws_wnd"].split(",")
      self.ws_wnd_f, self.ws_wnd_n = map(int, (self.dict_args["ws_wnd"].split(",")))
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
    return



class PbsScriptCreator:
  """Given the input arg parameters, generate a PBS script body."""
  def __init__(self, param_reader):
    self.param_reader = param_reader
    self.dict_args = param_reader.dict_args
    self.user = self.dict_args['user']

  def CmdFinalCleanUpTempDir(self):
    cmd = '#Final clean up, remove the files at tmp folder.'
    cmd += "\nfind %s/ -maxdepth 1 -type f -user %s -exec rm {} \\;\n" % (self.param_reader.path_tmp, self.user)
    return cmd

  def CreateScriptForNewJob(self, script_filename_stem):
    """Construct the pbs script from script_template.
    Args:
      script_filename_stem: The basename (without extension) for the new script name.
      """
    path_out = self.param_reader.path_out
    prefix = self.param_reader.prefix
    fname_template_script = self.param_reader.fname_template_script
    self.fn_script = '%s/%s-%s.sh' % (path_out, prefix, script_filename_stem)
    self.fn_log = '%s/%s-%s.log' % (path_out, prefix, script_filename_stem)
    cmd1 = "cp %s %s" % (fname_template_script, self.fn_script)
    sepbase.RunShellCmd(cmd1)
    nnodes = int(self.dict_args.get('nnodes',1))  # By default, use one node per job
    if nnodes != 0:  # Need to change the number of nodes used for this job
      cmd1 = ("sed -i 's/#PBS\ -l\ nodes=1/#PBS\ -l\ nodes=%d/g'   %s" %
              (nnodes, self.fn_script))
      sepbase.RunShellCmd(cmd1)
    # Change jobname for better readability.
    cmd0 = "sed -i '/#PBS -N/c\#PBS -N %s' %s" % (script_filename_stem, self.fn_script)
    # Redirect PBS output, change the entire PBS -o and -e line
    cmd1 = "sed -i '/#PBS -o/c\#PBS -o %s' %s" % (self.fn_log, self.fn_script)
    cmd2 = "sed -i '/#PBS -e/c\#PBS -e %s' %s" % (self.fn_log, self.fn_script)  
    sepbase.RunShellCmd(cmd0+'\n'+cmd1+'\n'+cmd2)
    return


class WeiScriptor:
  """Given the input arg parameters, generate scripts that performs a WEI (Wave equation inversion) operation."""
  def __init__(self, param_reader):
    self.param_reader = param_reader
    self.dict_args = param_reader.dict_args
    self.sz_shotrange = None

  def NewJob(self, sz_shotrange):
    """Call this func first everytime you start a new job."""
    self.sz_shotrange = sz_shotrange
    path_out = self.param_reader.path_out
    prefix = self.param_reader.prefix
    self.fn_imgh  = "%s/%s-%s.H"  %(path_out, prefix, sz_shotrange)
    self.fnt_imgh_list = []
    return

  def CmdMigrationPerShot(self, ish, image_domains = (None,)*6):
    '''Generate shell cmd for doing the migration.
    image_domains: is a tuple of (xmin,xmax,ymin,ymax,zmin,zmax) that indicate the imaging domain.'''
    cmd = '# Perform migration for the current shot.\n'
    path_tmp = self.param_reader.path_tmp
    prefix = self.param_reader.prefix
    self.fnt_imgh = '%s/imgh-%s-%04d.H' % (path_tmp,prefix,ish)
    self.fnt_imgh_list.append(self.fnt_imgh)
    wem_bin_path = self.dict_args['TANG_BIN']
    cmd += "%s/bwi-wem3d-Zh.x %s %s mode=imgadj crec=%s csou=%s bimg=%s bvel=%s datapath=%s/ memchk=n report=y " % (
        wem_bin_path, self.dict_args['MIG_PAR_WAZ3D'], self.dict_args['SS_OFFSET_PAR'], self.fnt_crec, self.fnt_csou, self.fnt_imgh,self.fnt_bvel, path_tmp)
    xmin, xmax = image_domains[0:2]
    ymin, ymax = image_domains[2:4]
    zmin, zmax = image_domains[4:6]
    if xmin is not None:
      cmd += " image_xmin=%.1f image_xmax=%.1f image_ymin=%.1f image_ymax=%.1f " % (
          xmin,xmax,ymin,ymax)
    if zmin is not None:
      cmd += " image_zmin=%.1f image_zmax=%.1f " % (zmin,zmax)
    return cmd + CheckPrevCmdResultCShellScript(cmd)


  def CmdCombineMultipleOutputSepHFiles(sz_shotrange, local_sepH_list, global_output_filename, combine_pars=""):
    cmd = '# Combine the results from multiple shots into one.\n'
    path_out = self.param_reader.path_out
    prefix = self.param_reader.prefix
    n = len(local_sepH_list)
    if n == 1:
      cmd1 = "time Cp %s %s\n" % (local_sepH_list[0],global_output_filename)
    else:
      fn_tflist = "%s/%s-%s.flist"%(path_out,prefix,sz_shotrange)
      fp_tflist = open(fn_tflist,"w")
      fp_tflist.write("\n".join(local_sepH_list))
      fp_tflist.close()
      #axis 3,4,5 are (x,y,z)
      cmd1 = "time %s/Combine.x <%s filelist=%s output=%s %s \n" % (
          dict_args['YANG_BIN'],local_sepH_list[0],fn_tflist, global_output_filename,combine_pars)
    # The combine process could go wrong, therefore add a conditional clause
    cmd += (cmd1+CheckPrevCmdResultCShellScript(cmd1))
    return cmd

  def CmdBornModelingPerShot(self, ish):
    cmd = '# Do born modeling for the current shot.\n' 
    path_tmp = self.param_reader.path_tmp
    src_type = self.param_reader.source_type
    self.fnt_crec = '%s/crec-model-%04d.H' % (path_tmp,ish)
    wem_bin_path = self.dict_args['TANG_BIN']
    if src_type == 'plane':
      cmd1 = "time %s/bwi-wem3d-Zh.x %s %s mode=imgfwd crec=%s csou=%s bimg=%s bvel=%s datapath=%s/" % (
          wem_bin_path, self.dict_args['MIG_PAR_WAZ3D'], self.dict_args['GEOM_GXY'], self.fnt_crec, self.fnt_csou, self.fnt_bimgh,self.fnt_bvel, path_tmp)
    else:
      cmd1 = "time %s/bwi-wem3d-Zh.x %s %s mode=imgfwd crec=%s csou=%s bimg=%s bvel=%s datapath=%s/" % (
          wem_bin_path, self.dict_args['MIG_PAR_WAZ3D'], self.dict_args['GEOM_GXY'], self.fnt_crec, self.fnt_csou, self.fnt_bimgh,self.fnt_bvel, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def ConceiveCommand(self, ish):
    '''Conceive all the cmd that will be used in the script.'''
    self.fnt_crec = "crec-%04d.H" % ish
    pass

  def CmdCpbvelForEachJob(self):
    cmd = '# Copy the velocity file to local disk.\n'
    fn_v3d = self.param_reader.fn_v3d
    path_tmp = self.param_reader.path_tmp
    fnt_bvel = '%s/vel-%s.H' % (path_tmp,self.sz_shotrange)
    # For cping base velocity to local folder.
    cmd1 = "time Cp <%s >%s datapath=%s/" % (fn_v3d, fnt_bvel, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpbimgForEachJob(self):
    cmd = '# Copy the background image(reflectivity model) file to local disk.\n'
    path_tmp = self.param_reader.path_tmp
    self.fn_bimgh = abspath(self.dict_args["bimgh"])
    self.fnt_bimgh = '%s/bimgh-%s.H' % (path_tmp,self.sz_shotrange)
    # For cping base imgh to local folder.
    cmd1 = "time Cp <%s >%s datapath=%s/" % (self.fn_bimgh,self.fnt_bimgh, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpbvelForEachJob(self):
    cmd = '# Copy the background vel model file to local disk.\n'
    fn_v3d = self.param_reader.fn_v3d
    path_tmp = self.param_reader.path_tmp
    self.fnt_bvel = '%s/vel-%s.H' % (path_tmp,self.sz_shotrange)
    cmd1 = "time Cp <%s >%s datapath=%s/" % (fn_v3d, self.fnt_bvel, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCpCrecForEachShot(self, ish, fn_shot_crec):
    '''Copy the related crec binaries (e.g. data) to local folder, this applies to
    the imaging case not modeling case.'''
    cmd = '# Copy the data of current shot to local disk.\n'
    path_tmp = self.path_tmp
    ws_wnd_f, ws_wnd_n = self.param_reader.ws_wnd_f, self.param_reader.ws_wnd_n
    if self.ws_wnd_n is not None:
      cmd1 = "Window3d <%s f3=%d n3=%d >%s squeeze=n datapath=%s/ " % (
          fn_shot_crec, self.ws_wnd_f, self.ws_wnd_n, self.fnt_crec, path_tmp)
    else:
      cmd1 = "Cp %s %s datapath=$%s/ "% (fn_shot_crec,fnt_crec, path_tmp)
    return cmd + cmd1+CheckPrevCmdResultCShellScript(cmd1)

  def CmdCsouForEachShot(self,ish):
    '''Generate the command for each shot.'''
    cmd = '# Generate the source file for current shot on local disk.\n'
    path_tmp = self.param_reader.path_tmp
    # If user only select a portion of frequencies to migrate/compute/model, w_f,w_n
    ws_wnd_f, ws_wnd_n = self.param_reader.ws_wnd_f, self.param_reader.ws_wnd_n
    fn_csou = self.param_reader.fn_csou
    fnt_csou = "%s/csou-plane-%04d.H" % (path_tmp, ish)  # Append the filename fn_csou with shotIndex as the new filename.
    self.fnt_csou = fnt_csou
    if self.param_reader.source_type == 'plane':
      # The source func for each shot is different. Needs to do Window based on it.
      n4 = int(sepbase.get_sep_axis_params(fn_csou,4)[0])
      f5 = ish / n4
      f4 = ish % n4
      if ws_wnd_n is not None:
        cmd2 = "Window3d <%s f3=%d n3=%d n4=1 n5=1 f4=%d f5=%d >%s squeeze=n datapath=%s/ " % (
            fn_csou,ws_wnd_f,ws_wnd_n,f4,f5,fnt_csou,path_tmp)
      else:
        cmd2 = "Window3d <%s n4=1 n5=1 f4=%d f5=%d >%s squeeze=n datapath=%s/ "%(fn_csou,f4,f5,fnt_csou,path_tmp)
    else:  # Point Source
      if ws_wnd_n is not None:
        cmd2 = "Window3d <%s f3=%d n3=%d >%s squeeze=n datapath=%s/ " % (
            fn_csou,ws_wnd_f,ws_wnd_n,fnt_csou,path_tmp)
      else:
        cmd2 = "Cp %s %s datapath=%s/ "%(fn_csou, fnt_csou, path_tmp)
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
      total_jobs_cap: The cap for running jobs + pending jobs for each queue, (for the sake of code simplicity, this is a per-queue cap).
    """
    assert len(queues_info) > 0
    self._queues_info = queues_info[:]
    if user is None:
      self._user_name = os.environ['USER']
    else:
      self._user_name = user
    if total_jobs_cap is None:
      self._total_jobs_cap = 10000  # Number should be big enough.
    else:
      self._total_jobs_cap = total_jobs_cap

  def WaitOnAllJobsFinish(self, grep_pattern = None):
    '''The function will block our script until all related jobs (that can be found under the current user and matches the grep_pattern) have been finished.
    Args:
      grep_pattern: An optional pattern string that will be used to find all jobs under the given user and matches the grep_pattern.'''
    icnt = 0
    while True:
      if not grep_pattern:
        cmd = "qstat -a | grep %s | wc -l " % (self._user_name)
      else:
        cmd = "qstat -a | grep %s | grep %s | wc -l " % (self._user_name, grep_pattern)
      stat1,out1=commands.getstatusoutput(cmd)
      if int(out1) > 0:
        icnt += 1
        if icnt == 1: print "Wait On All Jobs to Finish..."
        time.sleep(120)
      else:
        break
    return

  def SubmitJob(self, fn_script):
    #Submit the job script to pbs system by looking at if there are enough running jobs
    num_queues = len(self._queues_info)
    i_queue = 0
    while True:
      queue_name, queue_cap = self._queues_info[i_queue]
      print "In SubmitJob: ", num_queues, i_queue, queue_name, queue_cap
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
      print "jobs status in the queue, R/ Q:C, %d/ %d:%d" % (jobR, jobQ, jobC)
      njob_pending = jobQ + jobC
      njob_total = njob_pending + jobR
      if njob_pending < queue_cap and njob_total < self._total_jobs_cap:
        cmd1 = "qsub -q %s %s" % (queue_name, fn_script)
        print line_no(), ("submitting job %s to Queue:%s" %
                          (fn_script, queue_name))
        stat1, out1 = commands.getstatusoutput(cmd1)
        if stat1 != 0:
          err("submit job failed, msg=%d,%s" % (stat1,out1))
        os.system("sleep 15")  # Stagger the job start-off time a bit.
        break
      else:
        # if not last queue, then try next queue
        if i_queue != num_queues-1:
          i_queue = (i_queue+1) % num_queues
        else:  # back-off for a while before retrying
          print "Waiting on the pbs queue..."
          os.system("sleep 60")  # Sleep a while (secs) before do the query again.
          # Then start polling the first queue again.
          i_queue = 0
    return

