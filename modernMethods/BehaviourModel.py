import numpy as np
from random import shuffle


class MarkovChain:
    def __init__(self, states, transition_list):
        assert len(states) == len(transition_list)
        P = np.zeros([len(states), len(states)])
        for i, p_list in enumerate(transition_list):
            assert len(p_list) == len(states) - 1
            P[i, i] = 1 - sum(p_list)
            for j, p in enumerate(p_list):
                if j >= i:
                    P[i, j+1] = p_list[j]
                else:
                    P[i, j] = p_list[j]

        self.states = states
        self.P = P
        self.state = None

    def set_state(self, state):
        #self.state = np.reshape(state, [1, np.shape(self.P)[0]])
        self.state = state

    def take_step(self):
        self.state = self.state @ self.P
        for n in range(np.shape(self.state)[0]):
            self.state[n, :] = np.random.multinomial(1, self.state[n, :], 1)
        return self.state

    def take_n_steps(self, n):
        self.state = self.state @ np.linalg.matrix_power(self.P, n)
        return self.state

    def sample_rollouts(self, initial_state, n_rollouts, T):
        state_history = np.zeros([n_rollouts, T])
        self.set_state(initial_state)
        for t in range(T):
            s = np.squeeze(self.take_step())
            state_history[:, t] = np.argmax(s, axis=1)
            #print(np.random.choice(np.arange(1, np.shape(self.states)[0]), [n_rollouts], True, self.state.T))
        return state_history


class NoiseModelFN:

    def __init__(self, states, transition_probs, initial_state, p1, p2, p3, p4):
        self.states = states
        self.transition_probs = transition_probs
        self.state = initial_state
        self.wipe_markers()
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4

    def do_move(self):
        p = self.transition_probs[self.state]
        new_state = np.argmax(np.random.multinomial(1, p, 1))
        self.state = self.states[new_state]

    def wipe_markers(self):
        self.marker_ps = [None, None, None, None]
        self.marker_states = [None, None, None, None]

    def init_markers(self):
        p1 = np.random.uniform(self.p1[0], self.p1[1])
        p2 = np.random.uniform(self.p2[0], self.p2[1])
        p3 = np.random.uniform(self.p3[0], self.p3[1])
        p4 = np.random.uniform(self.p4[0], self.p4[1])
        p_vals = [p1, p2, p3, p4]
        shuffle(p_vals)
        self.marker_ps = p_vals

        self.marker_states = ['visible', 'visible', 'visible', 'visible']

    def sample_visibility(self):
        if self.state == 'all':
            if self.marker_ps[0] != None:
                self.wipe_markers()
            return np.ones([4])
        elif self.state == 'none':
            if self.marker_ps[0] != None:
                self.wipe_markers()
            return np.zeros([4])
        else:
            if self.marker_ps[0] == None:
                self.init_markers()

            for i in range(len(self.marker_ps)):
                if self.marker_states[i] == 'hidden':
                    if np.random.uniform(0, 1) < 1 - self.marker_ps[i]:
                        self.marker_states[i] = 'visible'
                else:
                    if np.random.uniform(0, 1) < self.marker_ps[i]:
                        self.marker_states[i] = 'hidden'

            ret = np.zeros([4])
            for i, s in enumerate(self.marker_states):
                if s == 'visible':
                    ret[i] = 1
            return ret

    def rollout(self, T, initial_state=None):
        self.wipe_markers()
        if initial_state != None:
            self.state = initial_state

        marker_visibility = []

        for t in range(T):
            self.do_move()
            marker_visibility.append(self.sample_visibility())

        return np.stack(marker_visibility, axis=0)


class NoiseModelFP:
    def __init__(self, states, transition_probs, initial_probs, scale, fp_prob, radius):
        self.states = states
        self.P = transition_probs
        self.init_p = initial_probs
        self.state = None
        self.init_state()
        self.fp_loc = []
        for i in range(len(self.states)):
            self.fp_loc.append(None)
        self.scale = scale
        self.fp_prob = fp_prob
        self.radius = radius

    def do_move(self):
        p = self.P[self.state]
        new_state = np.argmax(np.random.multinomial(1, p, 1))
        self.state = self.states[new_state]

    def init_state(self):
        self.state = int(np.argmax(np.random.multinomial(1, self.init_p, 1)))

    def wipe_fp_loc(self):
        self.fp_loc = []
        for i in range(len(self.states)):
            self.fp_loc.append(None)

    def sample_FPs(self):
        if self.state == 0:
            return []
        else:
            FPs = []
            for loc in self.fp_loc:
                if loc is not None:
                    if np.random.uniform(0, 1) < self.fp_prob:
                        #print(loc)
                        FPs.append(np.random.multivariate_normal(loc, self.scale*np.eye(3), 1))
            if not FPs:
                return []
            else:
                return np.concatenate(FPs, axis=0)

    def add_loc(self):
        theta = np.random.uniform(0, 3.14)
        phi = np.random.uniform(0, 2 * 3.14)
        x = self.radius * np.sin(theta) * np.cos(phi)
        y = self.radius * np.sin(theta) * np.sin(phi)
        z = self.radius * np.cos(theta)
        empty_locs = []
        for i,loc in enumerate(self.fp_loc):
            if loc is None:
                empty_locs.append(i)
        idx = np.random.choice(empty_locs)
        self.fp_loc[idx] = np.stack([x, y, z])

    def rollout(self, T):
        self.init_state()
        false_positives = []

        for t in range(T):
            self.do_move()
            if self.state == 0:
                self.wipe_fp_loc()
            elif self.state == 1:
                n_locs = 0
                for loc in self.fp_loc:
                    if loc is not None:
                        n_locs += 1
                if n_locs == 0:
                    self.add_loc()

                if n_locs == 2:
                    if np.random.uniform(0, 1) < 0.5:
                        self.fp_loc[0] = None
                    else:
                        self.fp_loc[1] = None
            elif self.state == 2:
                n_locs = 0
                for loc in self.fp_loc:
                    if loc is not None:
                        n_locs += 1
                if n_locs == 0:
                    self.add_loc()
                    self.add_loc()
                if n_locs == 1:
                    self.add_loc()
            else:
                raise AttributeError('Unexpected state!')
            false_positives.append(self.sample_FPs())
        return false_positives


noise_model_FP_states = [0, 1, 2]
noise_model_FP_transition_probs = np.array([[0.8, 0.2, 0], [0.2, 0.6, 0.2], [0, 0.8, 0.2]])
noise_model_FP_initial_probs = np.array([0, 0, 1])
fp_scale = 10
fp_prob = 0.5
radius = 150


def test_noise_FP_model():
    nMFP = NoiseModelFP(noise_model_FP_states, noise_model_FP_transition_probs, noise_model_FP_initial_probs,
                        fp_scale, fp_prob, radius)
    print(nMFP.rollout(100))


p1 = [0.1, 0.2]
p2 = [0.35, 0.6]
p3 = [0.6, 0.85]
p4 = [0.8, 0.95]
noise_model_states = ['all', 'some', 'none']
noise_model_transition_prob = {'all': [ 0.89, 0.1, 0.01], 'some': [0.02, 0.97, 0.01], 'none': [0.48, 0.48, 0.04]}
noise_model_initial_state = 'all'

def test_noise_model():
    nM = NoiseModelFN(noise_model_states, noise_model_transition_prob, noise_model_initial_state, p1, p2, p3, p4)
    print(nM.rollout(200))

#test_noise_model()





#old_noise_model_states = ['not flying, no wings', 'not flying, wing covers', 'flying, no wings' ,'flying, wing covers']
#
#p_nF_nFW = 0.004
#p_nF_F = 0.002
#p_nF_FW = 0.002
#
#p_nFW_nF = 0.05
#p_nFW_F = 0.002
#p_nFW_FW = 0.002
#
#p_F_nF = 0.01
#p_F_nFW = 0.01
#p_F_FW = 0.03
#
#p_FW_nF = 0.01
#p_FW_nFW = 0.01
#p_FW_F = 0.03
#
#old_noise_model_transition_prob = [[p_nF_nFW, p_nF_F, p_nF_FW],
#                               [p_nFW_nF, p_nFW_F, p_nFW_FW],
#                               [p_F_nF, p_F_nFW, p_F_FW],
#                               [p_FW_nF, p_FW_nFW, p_FW_F]]
#
#behaviour_model_states = ['sitting', 'starting', 'flying', 'landing', 'walking']
#p_sit_start = 0.005
#p_sit_walk = 0.02
#
#p_start_fly = 0.1
#
#p_fly_land = 0.02
#
#p_land_sit = 0.1
#p_land_walk = 0.1
#
#p_walk_sit = 0.05
#p_walk_start = 0.008
#
#behaviour_model_transition_prob = [[p_sit_start, 0, 0, p_sit_walk],
#                                   [0, p_start_fly, 0, 0],
#                                   [0, 0, p_fly_land, 0],
#                                   [p_land_sit, 0, 0, p_land_walk],
#                                   [p_walk_sit, p_walk_start, 0, 0]]
#
#N_ROLLOUTS = 2
#
#mc_behaviour_model = MarkovChain(behaviour_model_states, behaviour_model_transition_prob)
#initial_state = np.tile(np.array([[1, 0, 0, 0, 0]]), [N_ROLLOUTS, 1])
##mc_behaviour_model.set_state(initial_state)
##print(mc_behaviour_model.P)
##print(mc_behaviour_model.sample_rollouts(initial_state, N_ROLLOUTS, 350))
##mc_noise_model = MarkovChain(noise_model_states, noise_model_transition_prob)
##print((mc_noise_model.P))
#
##P = mc_behaviour_model.P
##state = np.array([1, 0, 0, 0, 0])
#
##for t in range(100):
##    state = state @ P
##    print(t)
##    print(state)
#