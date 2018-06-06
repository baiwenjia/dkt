import matplotlib.pyplot as plt
import numpy as np
import sys
import scipy.optimize

class SigmoidModel(object):
  plt.interactive(False)

  def __init__(self, X, Y, outFolder, plotter, priors, names_biomarkers=[], group=[]):
    # Initializing variables
    self.plotter = plotter
    self.priors = priors
    self.outFolder = outFolder
    self.expName = plotter.plotTrajParams['expName']
    self.names_biomarkers = names_biomarkers
    self.group = group
    self.nrSubj = len(X[0])
    self.nrBiomk = len(X)
    self.X_array = []
    self.Y_array = []
    self.X = X
    self.Y = Y
    self.N_obs_per_sub = []
    self.params_time_shift = np.ndarray([2, len(X[0])])

    # Time shift initialized to 0
    self.params_time_shift[0, :] = 0

    # Estension of the model will include a time scaling factor (fixed to 1 so far)
    self.params_time_shift[1, :] = 1

    self.X_array = [0 for _ in range(self.nrBiomk)]
    self.Y_array = [0 for _ in range(self.nrBiomk)]
    for b in range(self.nrBiomk):
      # Creating 1d arrays of individuals' time points and observations
      self.X_array[b] = np.array([np.float128(item) for sublist in X[b] for item in sublist]).reshape(-1,1)
      self.Y_array[b] = np.array([np.float128(item) for sublist in Y[b] for item in sublist]).reshape(-1,1)
      self.N_obs_per_sub.append([len(X[b][j]) for j in range(len(X[b]))])

    minX = np.min(self.X_array)
    maxX = np.max(self.X_array)
    self.updateMinMax(minX, maxX)

    self.parameters = [0 for b in range(self.nrBiomk)] # parameters of sigmoid trajectories
    for b in range(self.nrBiomk):
      minY = np.min(self.Y_array[b])
      maxY = np.max(self.Y_array[b])
      transitionTime = 4 * np.std(self.X_array[b])
      center = np.mean(self.X_array[b])
      trajParams = self.transfTrajParams(minY, transitionTime, center, maxY)
      variance = np.var(self.Y_array[b])
      self.parameters[b] = [trajParams, variance]

    scaledYarrayB = [self.applyScalingY(self.Y_array[b], b) for b in range(self.nrBiomk)]
    self.min_yB = np.array([np.min(scaledYarrayB[b].reshape(-1)) for b in range(self.nrBiomk)])
    self.max_yB = np.array([np.max(scaledYarrayB[b].reshape(-1)) for b in range(self.nrBiomk)])


  def transfTrajParams(self, minY, transitionTime, center, maxY):
    """
    :param params: [minY, transitionTime, center, maxY]
    :return: [a,b,c,d] form where a is the min-max range, b = -16/(a*tt) c = center d = minX
    """

    a = maxY - minY
    b = 16 / (a * transitionTime)
    c = center
    d = minY
    return [a,b,c,d]

  def applyScalingX(self, x_data, biomk=0):
    return x_data

  def applyScalingY(self, y_data, biomk):
    return y_data

  def applyScalingYAllBiomk(self, biomksXB):
    return biomksXB

  def getXsMinMaxRange(self, nrPoints=50):
    return np.linspace(self.minScX, self.maxScX, nrPoints).reshape([-1, 1])

  def updateMinMax(self, minX, maxX):
    self.minX = minX
    self.maxX = maxX
    self.minScX = self.applyScalingX(self.minX)
    self.maxScX = self.applyScalingX(self.maxX)

  def applyScalingXForward(self, x_data, biomk=0):
    return x_data

  def applyGivenScalingY(self, y_data, meanY, stdY):
    return (y_data - meanY) / stdY

  def applyScalingXzeroOneFwd(self, xs):
    return (xs - self.minScX) / \
           (self.maxScX - self.minScX)

  def applyScalingXzeroOneInv(self, xs):
    return xs * (self.maxScX - self.minScX) + self.minScX

  def getData(self):
    nrBiomk = len(self.X)
    nrSubj = len(self.X[0])
    XshiftedScaled = [[] for b in range(nrBiomk)]

    for b in range(nrBiomk):
      for s in range(nrSubj):
        XshiftedCurrSubj = np.array([self.X_array[b][k][0] for k in range(int(np.sum(
          self.N_obs_per_sub[b][:s])), np.sum(self.N_obs_per_sub[b][:s + 1]))])

        XshiftedScaled[b] += [self.applyScalingX(XshiftedCurrSubj)]

        assert XshiftedScaled[b][s].shape[0] == self.X[b][s].shape[0]
        assert XshiftedScaled[b][s].shape[0] == self.Y[b][s].shape[0]

    return XshiftedScaled, self.X, self.Y


  def getSubShiftsLong(self):
    return self.applyScalingX(self.params_time_shift[0])

  def getMinMaxY_B(self, extraDelta=0):
    ''' get minimum and maximum of Ys per biomarker'''
    deltaB = (self.max_yB - self.min_yB) * extraDelta

    return self.min_yB - deltaB, self.max_yB + deltaB


  def sigFunc(self, xs, theta):
    return theta[0] * np.power((1 + np.exp(-theta[1] * (xs - theta[2]))), -1) + theta[3]

  def trajObjFunc(self, params, X_arrayX, Y_arrayX):
    """
    computes the log posterior for the current biomarker
    :param X_arrayX: linearised array of DPS scores for current biomarker
    :param Y_arrayX: linearised array of measurements for current biomarker
    :param params: (4,) array of parameters for the sigmoid func
    :return:
    """

    # SSD
    logLik =  np.sum((Y_arrayX - self.sigFunc(X_arrayX, params)) ** 2)

    return logLik

  def unpack_parameters(self, params):
    return params[0], params[1]

  def estimVariance(self, params, X_arrayX, Y_arrayX):
    """
    computes the log posterior for the current biomarker
    :param X_arrayX: linearised array of DPS scores for current biomarker
    :param Y_arrayX: linearised array of measurements for current biomarker
    :param params: (4,) array of parameters for the sigmoid func
    :return:
    """

    # SSD/nrMeasurements
    variance =  np.sum((Y_arrayX - self.sigFunc(X_arrayX, params)) ** 2)/Y_arrayX.shape[0]
    return variance

  def estimTrajParams(self):
    # Method for optimization of GP parameters (weights, length scale, amplitude and noise term)

    for b in range(self.nrBiomk):
      initParams, initVariance = self.unpack_parameters(self.parameters[b])

      objectiveFun = lambda params: self.trajObjFunc(params, self.X_array[b], self.Y_array[b])
      resStruct = scipy.optimize.minimize(objectiveFun, initParams, method='Nelder-Mead',
                                          options={'disp': True})

      variance = self.estimVariance(resStruct.x, self.X_array[b], self.Y_array[b])

      self.parameters[b] = [resStruct.x, variance]

  def shiftObjFunc(self, params, time_shift_one_sub, sub):
    # Input: X, Y and a biomarker's parameters, current time-shift estimates
    # Output: log-posterior and time-shift gradient

    # Shifting data according to current time-shift estimate
    loglik = 0
    timeShiftPriorStd = 6
    timeShiftPriorMean = 0
    for b in range(self.nrBiomk):
      trajParams, variance = self.unpack_parameters(params[b])

      Xdata = time_shift_one_sub + self.X_array[b][int(np.sum(self.N_obs_per_sub[b][:sub])): \
                                                   np.sum(self.N_obs_per_sub[b][:sub + 1])]
      Ydata = self.Y_array[b][int(np.sum(self.N_obs_per_sub[b][:sub])):np.sum(self.N_obs_per_sub[b][:sub + 1])]
      Ypred = self.sigFunc(Xdata, trajParams)

      prior_time_shift = (time_shift_one_sub - timeShiftPriorMean) ** 2 / timeShiftPriorStd
      loglik += - 0.5 * (np.sum((Ydata - Ypred) ** 2) / variance) - prior_time_shift

    return loglik

  def estimSubjShifts(self):
    init_params = self.params_time_shift.copy()
    init_params[0] = np.zeros(len(init_params[0]))

    init_params_time_only = init_params[0]

    ######## calculate subject-nonspecific terms
    optimal_params_time_only = np.zeros(init_params_time_only.shape)

    nrSubj = self.nrSubj
    for s in range(nrSubj):
      objectiveFun = lambda time_shift_one_sub: -self.shiftObjFunc(self.parameters,
                       time_shift_one_sub, s)[0]

      options = {'disp': True, 'gtol': 1e-8}
      resStruct = scipy.optimize.minimize(objectiveFun, init_params_time_only[s], method='Nelder-Mead',
                                          options={'disp': True})

      optimal_params_time_only[s] = resStruct.x

    convTimeOnlyToTimePlusAcc = lambda params_time_shift_only_shift: \
      np.concatenate((params_time_shift_only_shift.reshape(1, -1),
                      np.ones((1, params_time_shift_only_shift.shape[0]))), axis=0)
    optimal_params = convTimeOnlyToTimePlusAcc(optimal_params_time_only)

    for l in range(1):
      self.params_time_shift[l] = self.params_time_shift[l] + optimal_params[l]

    for i in range(self.nrBiomk):
      Xdata = np.array([[100]])
      for sub in range(self.nrSubj):
        temp = self.X_array[i][int(np.sum(self.N_obs_per_sub[i][:sub])):np.sum(self.N_obs_per_sub[i][:sub + 1])]
        shifted_temp = (temp + optimal_params[0][sub])
        Xdata = np.hstack([Xdata, shifted_temp.T])

      self.X_array[i] = Xdata[0][1:].reshape([len(Xdata[0][1:]), 1])

    minX = np.float128(np.min([el for sublist in self.X_array for item in sublist for el in item]))
    maxX = np.float128(np.max([el for sublist in self.X_array for item in sublist for el in item]))
    self.updateMinMax(minX, maxX)


  def Optimize(self, N_global_iterations, Plot=True):
    # Global optimizer (Sigmoid parameters + time shift)
    fig = self.plotter.plotTraj(self)
    fig.savefig('%s/allTraj%d0_%s.png' % (self.outFolder, 0, self.expName))
    fig2 = self.plotter.plotCompWithTrueParams(self, replaceFig=True)
    fig2.savefig('%s/compTrueParams%d0_%s.png' % (self.outFolder, 0, self.expName))


    for i in range(N_global_iterations):

      print("Optimizing time shift")
      self.estimSubjShifts()

      if Plot:
        fig = self.plotter.plotTraj(self)
        fig.savefig('%s/allTraj%d0_%s.png' % (self.outFolder, i + 1, self.expName))
        fig2 = self.plotter.plotCompWithTrueParams(self)
        fig2.savefig('%s/compTrueParams%d0_%s.png' % (self.outFolder, i + 1, self.expName))

      self.estimTrajParams()
      print("Current penalty parameters: ")

      if Plot:
        fig = self.plotter.plotTraj(self)
        fig.savefig('%s/allTraj%d1_%s.png' % (self.outFolder, i + 1, self.expName))
        fig2 = self.plotter.plotCompWithTrueParams(self)
        fig2.savefig('%s/compTrueParams%d1_%s.png' % (self.outFolder, i + 1, self.expName))


  def predictBiomkWithParams(self, newX, params):

    deltaX = 0.2 * (self.maxScX - self.minScX)
    if not (self.minScX - deltaX <= np.min(newX) <= self.maxScX + deltaX):
      print('newX', newX)
      print('self.minScX', self.minScX)
      print('self.maxScX', self.maxScX)
      raise ValueError('newX not in the correct range. check the scaling')

    xsScaled = self.applyScalingXForward(newX.reshape(-1), biomk=0)  # arbitrary space ->[0,1]

    predictedBiomksXB = np.zeros((xsScaled.shape[0], self.nrBiomk))
    for b in range(self.nrBiomk):
      trajParams, variance = self.unpack_parameters(params[b])
      predictedBiomksXB[:, b] = self.sigFunc(xsScaled, trajParams)

    return self.applyScalingYAllBiomk(predictedBiomksXB)

  def predictBiomk(self, newX):
    return self.predictBiomkWithParams(newX, self.parameters)

  def sampleTrajPost(self, newX, biomarker, nrSamples):
    '''
    sample trajectory posterior

    :param newX:
    :param biomarker:
    :param nrSamples:
    :return:
    '''

    xsScaled = self.applyScalingXForward(newX.reshape(-1))  # arbitrary space ->[0,1]

    trajSamplesXS = np.zeros((xsScaled.shape[0], nrSamples))
    trajParams, variance = self.unpack_parameters(self.parameters[biomarker])

    for i in range(nrSamples):
      trajSamplesXS[:, i] = self.sigFunc(xsScaled, trajParams)

    return self.applyScalingY(trajSamplesXS, biomarker)
