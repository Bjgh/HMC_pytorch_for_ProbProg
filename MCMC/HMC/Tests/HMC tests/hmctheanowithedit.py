#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 21 17:58:43 2017

@author: bradley
"""
from __future__ import absolute_import, print_function, division
import numpy

from theano import function, shared
from theano import tensor as TT
import theano
import theano.sandbox.rng_mrg

sharedX = (lambda X, name:
           shared(numpy.asarray(X, dtype=theano.config.floatX), name=name))


def kinetic_energy(vel):
    """Returns the kinetic energy associated with the given velocity
    and mass of 1.

    Parameters
    ----------
    vel: theano matrix
        Symbolic matrix whose rows are velocity vectors.

    Returns
    -------
    return: theano vector
        Vector whose i-th entry is the kinetic entry associated with vel[i].

    """
    #==============================================================================
#     The kintetic energy will be the laplace momentum in  the discrete case
#==============================================================================
    return 0.5 * (vel ** 2).sum(axis=1)


def hamiltonian(pos, vel, energy_fn):
    """
    Returns the Hamiltonian (sum of potential and kinetic energy) for the given
    velocity and position.

    Parameters
    ----------
    pos: theano matrix
        Symbolic matrix whose rows are position vectors.
    vel: theano matrix
        Symbolic matrix whose rows are velocity vectors.
    energy_fn: python function
        Python function, operating on symbolic theano variables, used tox
        compute the potential energy at a given position.

    Returns
    -------
    return: theano vector
        Vector whose i-th entry is the Hamiltonian at position pos[i] and
        velocity vel[i].
    """
    # assuming mass is 1
    return energy_fn(pos) + kinetic_energy(vel)


def metropolis_hastings_accept(energy_prev, energy_next, s_rng):
    """
    Performs a Metropolis-Hastings accept-reject move.

    Parameters
    ----------
    energy_prev: theano vector
        Symbolic theano tensor which contains the energy associated with the
        configuration at time-step t.
    energy_next: theano vector
        Symbolic theano tensor which contains the energy associated with the
        proposed configuration at time-step t+1.
    s_rng: theano.tensor.shared_randomstreams.RandomStreams
        Theano shared random stream object used to generate the random number
        used in proposal.

    Returns
    -------
    return: boolean
        True if move is accepted, False otherwise
    """
    ediff = energy_prev - energy_next
    return (TT.exp(ediff) - s_rng.uniform(size=energy_prev.shape)) >= 0


def simulate_dynamics(initial_pos, initial_vel, stepsize, n_steps, energy_fn):
    """
    Return final (position, velocity) obtained after an `n_steps` leapfrog
    updates, using Hamiltonian dynamics.

    Parameters
    ----------
    initial_pos: shared theano matrix
        Initial position at which to start the simulation
    initial_vel: shared theano matrix
        Initial velocity of particles
    stepsize: shared theano scalar
        Scalar value controlling amount by which to move
    energy_fn: python function
        Python function, operating on symbolic theano variables, used to
        compute the potential energy at a given position.

    Returns
    -------
    rval1: theano matrix
        Final positions obtained after simulation
    rval2: theano matrix
        Final velocity obtained after simulation
    """
#==============================================================================
# WITH PYTORCH WE CAN SIMPLY CONVERT THIS TO A FOR LOOP AND WHILE LOOP! 
#==============================================================================
    def leapfrog(pos, vel, step):
        """
        Inside loop of Scan. Performs one step of leapfrog update, using
        Hamiltonian dynamics.

        Parameters
        ----------
        pos: theano matrix
            in leapfrog update equations, represents pos(t), position at time t
        vel: theano matrix
            in leapfrog update equations, represents vel(t - stepsize/2),
            velocity at time (t - stepsize/2)
        step: theano scalar
            scalar value controlling amount by which to move

        Returns
        -------
        rval1: [theano matrix, theano matrix]
            Symbolic theano matrices for new position pos(t + stepsize), and
            velocity vel(t + stepsize/2)
        rval2: dictionary
            Dictionary of updates for the Scan Op
        """
        # from pos(t) and vel(t-stepsize//2), compute vel(t+stepsize//2)
        #==============================================================================
#         THE LINE BELOW HAS TO BE IMPLEMENTED IN TORCH
#==============================================================================
        dE_dpos = TT.grad(energy_fn(pos).sum(), pos)
        new_vel = vel - step * dE_dpos
        # from vel(t+stepsize//2) compute pos(t+stepsize)
        new_pos = pos + step * new_vel
#==============================================================================
#         Will not   be returning dictionary in pytorch
#==============================================================================
        return [new_pos, new_vel], {}

    # compute velocity at time-step: t + stepsize//2
    initial_energy = energy_fn(initial_pos)
    #==============================================================================
#     THE LINE BELOW HAS TO BE IMPLEMENTED IN TORCH
#==============================================================================
    dE_dpos = TT.grad(initial_energy.sum(), initial_pos)
    vel_half_step = initial_vel - 0.5 * stepsize * dE_dpos

    # compute position at time-step: t + stepsize
    pos_full_step = initial_pos + stepsize * vel_half_step

    # perform leapfrog updates: the scan op is used to repeatedly compute
    # vel(t + (m-1/2)*stepsize) and pos(t + m*stepsize) for m in [2,n_steps].
    #==============================================================================
#     Implement with a while LOOP, AS LONG AS THE INPUT IS A VARIABLE
#    THERE WILL BE NO PROBLEMS 
#==============================================================================
    (all_pos, all_vel), scan_updates = theano.scan(
        leapfrog,
        outputs_info=[
            dict(initial=pos_full_step),
            dict(initial=vel_half_step),
        ],
        non_sequences=[stepsize],
        n_steps=n_steps - 1)
    final_pos = all_pos[-1]
    final_vel = all_vel[-1]
    # NOTE: Scan always returns an updates dictionary, in case the
    # scanned function draws samples from a RandomStream. These
    # updates must then be used when compiling the Theano function, to
    # avoid drawing the same random numbers each time the function is
    # called. In this case however, we consciously ignore
    # "scan_updates" because we know it is empty.
    assert not scan_updates

    # The last velocity returned by scan is vel(t +
    # (n_steps - 1 / 2) * stepsize) We therefore perform one more half-step
    # to return vel(t + n_steps * stepsize)
    energy = energy_fn(final_pos)
    final_vel = final_vel - 0.5 * stepsize * TT.grad(energy.sum(), final_pos)

    # return new proposal state
    return final_pos, final_vel


# start-snippet-1
def hmc_move(s_rng, positions, energy_fn, stepsize, n_steps):
    """
    This function performs one-step of Hybrid Monte-Carlo sampling. We start by
    sampling a random velocity from a univariate Gaussian distribution, perform
    `n_steps` leap-frog updates using Hamiltonian dynamics and accept-reject
    using Metropolis-Hastings.

    Parameters
    ----------
    s_rng: theano shared random stream
        Symbolic random number generator used to draw random velocity and
        perform accept-reject move.
    positions: shared theano matrix
        Symbolic matrix whose rows are position vectors.
    energy_fn: python function
        Python function, operating on symbolic theano variables, used to
        compute the potential energy at a given position.
    stepsize:  shared theano scalar
        Shared variable containing the stepsize to use for `n_steps` of HMC
        simulation steps.
    n_steps: integer
        Number of HMC steps to perform before proposing a new position.

    Returns
    -------
    rval1: boolean
        True if move is accepted, False otherwise
    rval2: theano matrix
        Matrix whose rows contain the proposed "new position"
    """
    # end-snippet-1 start-snippet-2
    # sample random velocity
    #==============================================================================
#     When implementing in pytorch, we need to sample from a normal accross
#     multiple dimensions. All s_rng.normal does, is return an array 'tensor'
#     of normal distrubuted random variables. So in pytorch, we just need a
#     momentum that is a momentum tensor of random numbers of size N x D
#==============================================================================
    initial_vel = s_rng.normal(size=positions.shape)
    # end-snippet-2 start-snippet-3
    # perform simulation of particles subject to Hamiltonian dynamics
    final_pos, final_vel = simulate_dynamics(
        initial_pos=positions,
        initial_vel=initial_vel,
        stepsize=stepsize,
        n_steps=n_steps,
        energy_fn=energy_fn
    )
    # end-snippet-3 start-snippet-4
    # accept/reject the proposed move based on the joint distribution
    accept = metropolis_hastings_accept(
        energy_prev=hamiltonian(positions, initial_vel, energy_fn),
        energy_next=hamiltonian(final_pos, final_vel, energy_fn),
        s_rng=s_rng
    )
    # end-snippet-4
    return accept, final_pos


# start-snippet-5
def hmc_updates(positions, stepsize, avg_acceptance_rate, final_pos, accept,
                target_acceptance_rate, stepsize_inc, stepsize_dec,
                stepsize_min, stepsize_max, avg_acceptance_slowness):
    """This function is executed after `n_steps` of HMC sampling
    (`hmc_move` function). It creates the updates dictionary used by
    the `simulate` function. It takes care of updating: the position
    (if the move is accepted), the stepsize (to track a given target
    acceptance rate) and the average acceptance rate (computed as a
    moving average).

    Parameters
    ----------
    positions: shared variable, theano matrix
        Shared theano matrix whose rows contain the old position
    stepsize: shared variable, theano scalar
        Shared theano scalar containing current step size
    avg_acceptance_rate: shared variable, theano scalar
        Shared theano scalar containing the current average acceptance rate
    final_pos: shared variable, theano matrix
        Shared theano matrix whose rows contain the new position
    accept: theano scalar
        Boolean-type variable representing whether or not the proposed HMC move
        should be accepted or not.
    target_acceptance_rate: float
        The stepsize is modified in order to track this target acceptance rate.
    stepsize_inc: float
        Amount by which to increment stepsize when acceptance rate is too high.
    stepsize_dec: float
        Amount by which to decrement stepsize when acceptance rate is too low.
    stepsize_min: float
        Lower-bound on `stepsize`.
    stepsize_min: float
        Upper-bound on `stepsize`.
    avg_acceptance_slowness: float
        Average acceptance rate is computed as an exponential moving average.
        (1-avg_acceptance_slowness) is the weight given to the newest
        observation.

    Returns
    -------
    rval1: dictionary-like
        A dictionary of updates to be used by the `HMC_Sampler.simulate`
        function.  The updates target the position, stepsize and average
        acceptance rate.

    """

    # POSITION UPDATES #
    # broadcast `accept` scalar to tensor with the same dimensions as
    # final_pos.
    accept_matrix = accept.dimshuffle(0, *(('x',) * (final_pos.ndim - 1)))
    # if accept is True, update to `final_pos` else stay put
    #==============================================================================
#     Implement with if statement with pytorch tensor. 
#==============================================================================
    new_positions = TT.switch(accept_matrix, final_pos, positions)
    # end-snippet-5 start-snippet-7
    # STEPSIZE UPDATES #
    # if acceptance rate is too low, our sampler is too "noisy" and we reduce
    # the stepsize. If it is too high, our sampler is too conservative, we can
    # get away with a larger stepsize (resulting in better mixing).
    #==============================================================================
#     Implement with if statement with pytorch tensor. 
#==============================================================================
    _new_stepsize = TT.switch(avg_acceptance_rate > target_acceptance_rate,
                              stepsize * stepsize_inc, stepsize * stepsize_dec)
    # maintain stepsize in [stepsize_min, stepsize_max]
    #==============================================================================
#     Will have to change clip, all it does is ensures that if the step size
#       is outside of the given range, then we assign the step value to the
#       value that is closet to the bound.
#==============================================================================
    new_stepsize = TT.clip(_new_stepsize, stepsize_min, stepsize_max)

    # end-snippet-7 start-snippet-6
    # ACCEPT RATE UPDATES #
    # perform exponential moving average
    #==============================================================================
#     In pytorch we can jjust use the '+' operator.  Will have to use the torch
#     operator for the mean. 
#==============================================================================
    mean_dtype = theano.scalar.upcast(accept.dtype, avg_acceptance_rate.dtype)
    new_acceptance_rate = TT.add(
        avg_acceptance_slowness * avg_acceptance_rate,
        (1.0 - avg_acceptance_slowness) * accept.mean(dtype=mean_dtype))
    # end-snippet-6 start-snippet-8
    return [(positions, new_positions),
            (stepsize, new_stepsize),
            (avg_acceptance_rate, new_acceptance_rate)]
    # end-snippet-8


class HMC_sampler(object):
    """
    Convenience wrapper for performing Hybrid Monte Carlo (HMC). It creates the
    symbolic graph for performing an HMC simulation (using `hmc_move` and
    `hmc_updates`). The graph is then compiled into the `simulate` function, a
    theano function which runs the simulation and updates the required shared
    variables.

    Users should interface with the sampler thorugh the `draw` function which
    advances the markov chain and returns the current sample by calling
    `simulate` and `get_position` in sequence.

    The hyper-parameters are the same as those used by Marc'Aurelio's
    'train_mcRBM.py' file (available on his personal home page).
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        # could use for key, value in kwargs.items():
#            setattr(self,key,value)

    @classmethod
    def new_from_shared_positions(
        cls,
        shared_positions,
        energy_fn,
        initial_stepsize=0.01,
        target_acceptance_rate=.9,
        n_steps=20,
        stepsize_dec=0.98,
        stepsize_min=0.001,
        stepsize_max=0.25,
        stepsize_inc=1.02,
        # used in geometric avg. 1.0 would be not moving at all
        avg_acceptance_slowness=0.9,
        seed=12345
    ):
        """
        :param shared_positions: theano ndarray shared var with
            many particle [initial] positions

        :param energy_fn:
            callable such that energy_fn(positions)
            returns theano vector of energies.
            The len of this vector is the batchsize.

            The sum of this energy vector must be differentiable (with
            theano.tensor.grad) with respect to the positions for HMC
            sampling to work.

        """
        # allocate shared variables
        stepsize = sharedX(initial_stepsize, 'hmc_stepsize')
        avg_acceptance_rate = sharedX(target_acceptance_rate,
                                      'avg_acceptance_rate')
        s_rng = theano.sandbox.rng_mrg.MRG_RandomStreams(seed)

        # define graph for an `n_steps` HMC simulation
        accept, final_pos = hmc_move(
            s_rng,
            shared_positions,
            energy_fn,
            stepsize,
            n_steps)

        # define the dictionary of updates, to apply on every `simulate` call
        simulate_updates = hmc_updates(
            shared_positions,
            stepsize,
            avg_acceptance_rate,
            final_pos=final_pos,
            accept=accept,
            stepsize_min=stepsize_min,
            stepsize_max=stepsize_max,
            stepsize_inc=stepsize_inc,
            stepsize_dec=stepsize_dec,
            target_acceptance_rate=target_acceptance_rate,
            avg_acceptance_slowness=avg_acceptance_slowness)

        # compile theano function
        simulate = function([], [], updates=simulate_updates)

        # create HMC_sampler object with the following attributes ...
        return cls(
            positions=shared_positions,
            stepsize=stepsize,
            stepsize_min=stepsize_min,
            stepsize_max=stepsize_max,
            avg_acceptance_rate=avg_acceptance_rate,
            target_acceptance_rate=target_acceptance_rate,
            s_rng=s_rng,
            _updates=simulate_updates,
            simulate=simulate)

    def draw(self, **kwargs):
        """
        Returns a new position obtained after `n_steps` of HMC simulation.

        Parameters
        ----------
        kwargs: dictionary
            The `kwargs` dictionary is passed to the shared variable
            (self.positions) `get_value()` function.  For example, to avoid
            copying the shared variable value, consider passing `borrow=True`.

        Returns
        -------
        rval: numpy matrix
            Numpy matrix whose of dimensions similar to `initial_position`.
       """
        self.simulate()
        return self.positions.get_value(borrow=False)
def sampler_on_nd_gaussian(sampler_cls, burnin, n_samples, dim=3):
    batchsize = 1

    rng = numpy.random.RandomState(123)

    # Define a covariance and mu for a gaussian
    mu = numpy.array(rng.rand(dim) * 10, dtype=theano.config.floatX)
    cov = numpy.array(rng.rand(dim, dim), dtype=theano.config.floatX)
    cov = (cov + cov.T) / 2.
    cov[numpy.arange(dim), numpy.arange(dim)] = 1.0
    cov_inv = numpy.linalg.inv(cov)

    # Define energy function for a multi-variate Gaussian
    def gaussian_energy(x):
        return 0.5 * (theano.tensor.dot((x - mu), cov_inv) *
                      (x - mu)).sum(axis=1)

    # Declared shared random variable for positions
    position = rng.randn(batchsize, dim).astype(theano.config.floatX)
    position = theano.shared(position)

    # Create HMC sampler
    sampler = sampler_cls(position, gaussian_energy,
                          initial_stepsize=1e-3, stepsize_max=0.5)

    # Start with a burn-in process
    garbage = [sampler.draw() for r in range(burnin)]  # burn-in Draw
    # `n_samples`: result is a 3D tensor of dim [n_samples, batchsize,
    # dim]
    _samples = numpy.asarray([sampler.draw() for r in range(n_samples)])
    # Flatten to [n_samples * batchsize, dim]
    samples = _samples.T.reshape(dim, -1).T
    print(samples,samples.shape)

    print('****** TARGET VALUES ******')
    print('target mean:', mu)
    print('target cov:\n', cov)

    print('****** EMPIRICAL MEAN/COV USING HMC ******')
    print('empirical mean: ', samples.mean(axis=0))
    print('empirical_cov:\n', numpy.cov(samples.T))

    print('****** HMC INTERNALS ******')
    print('final stepsize', sampler.stepsize.get_value())
    print('final acceptance_rate', sampler.avg_acceptance_rate.get_value())

    return sampler
sampler = sampler_on_nd_gaussian(HMC_sampler.new_from_shared_positions,
                                 burnin=1000, n_samples=1000, dim=2)
assert abs(sampler.avg_acceptance_rate.get_value() -
           sampler.target_acceptance_rate) < .1
assert sampler.stepsize.get_value() >= sampler.stepsize_min
assert sampler.stepsize.get_value() <= sampler.stepsize_max