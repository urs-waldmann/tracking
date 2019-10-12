import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
import gc
from pyquaternion import Quaternion as Quaternion
from vizTracking import visualize_tracking



weight_file = 'weights/pos_quat_lstm.npy'
generated_data_dir = 'generated_data'

drop_some_dets = True
use_const_pat = True

BATCH_SIZE = 50
NUM_EPOCHS = 100
LEARNING_RATE = 0.001
DROPOUT_RATE = 0.25

N_train = 100*BATCH_SIZE
N_eval = int(N_train/10)

T = 200

fc1_det_dim = 250
fc2_det_dim = 300
fc3_det_dim = 300
fc4_det_dim = 250
fc1_pat_dim = 200
fc2_pat_dim = 250
fc3_pat_dim = 150
#fc1_combo_dim = 300
#fc2_combo_dim = 100
hidden_dim = 75
fc_out_1_size = 30

# TODO: decay learning rate!
# TODO: save checkpoints, and complete logger

# TODO: move to google colab

# TODO: proper noise model, look at noise behaviour for individual markers inside pattern

# TODO: generate bird behaviour from VICON predictions, if not enough use kalman filter predictions

# TODO: generate a log function, which:
#       - stores model and task and hyperparams
#       - stores weights
#       - saves plot of training progress and raw data

# TODO: missing dtections and false positives

# TODO: try relative inupts instead of absolute detections

####################################################################################
######### REPORT #########
#
####################################################################################

class TrainingData():
    def __init__(self):
        self.X_train = None
        self.X_train_shuffled = None
        self.quat_train = None
        self.pos_train = None
        self.pattern_train = None

        self.X_test = None
        self.X_test_shuffled = None
        self.quat_test = None
        self.pos_test = None
        self.pattern_test = None

    def set_train_data(self, X, X_shuffled, quat, pos, pattern):
        self.X_train = X
        self.X_train_shuffled = X_shuffled
        self.quat_train = quat
        self.pos_train = pos
        self.pattern_train = pattern

    def set_test_data(self, X, X_shuffled, quat, pos, pattern):
        self.X_test = X
        self.X_test_shuffled = X_shuffled
        self.quat_test = quat
        self.pos_test = pos
        self.pattern_test = pattern

    def load_data(self, dir_name):
        self.X_train = np.load(dir_name + '_X_train.npy')
        self.X_train_shuffled = np.load(dir_name + '_X_train_shuffled.npy')
        self.quat_train = np.load(dir_name + '_quat_train.npy')
        self.pos_train = np.load(dir_name + '_pos_train.npy')
        self.pattern_train = np.load(dir_name + '_pattern_train.npy')

        self.X_test = np.load(dir_name + '_X_test.npy')
        self.X_test_shuffled = np.load(dir_name + '_X_test_shuffled.npy')
        self.quat_test = np.load(dir_name + '_quat_test.npy')
        self.pos_test = np.load(dir_name + '_pos_test.npy')
        self.pattern_test = np.load(dir_name + '_pattern_test.npy')

    def save_data(self, dir_name):
        np.save(dir_name + '_X_train.npy', self.X_train)
        np.save(dir_name + '_X_train_shuffled', self.X_train_shuffled)
        np.save(dir_name + '_quat_train', self.quat_train)
        np.save(dir_name + '_pos_train.npy', self.pos_train)
        np.save(dir_name + '_pattern_train.npy', self.pattern_train)

        np.save(dir_name + '_X_test.npy', self.X_test)
        np.save(dir_name + '_X_test_shuffled', self.X_test_shuffled)
        np.save(dir_name + '_quat_test', self.quat_test)
        np.save(dir_name + '_pos_test.npy', self.pos_test)
        np.save(dir_name + '_pattern_test.npy', self.pattern_test)

    def convert_to_torch(self):
        self.X_train = torch.from_numpy(self.X_train).float()
        self.X_train_shuffled = torch.from_numpy(self.X_train_shuffled).float()
        self.quat_train = torch.from_numpy(self.quat_train).float()
        self.pos_train = torch.from_numpy(self.pos_train).float()
        self.pattern_train = torch.from_numpy(self.pattern_train).float()

        self.X_test = torch.from_numpy(self.X_test).float()
        self.X_test_shuffled = torch.from_numpy(self.X_test_shuffled).float()
        self.quat_test = torch.from_numpy(self.quat_test).float()
        self.pos_test = torch.from_numpy(self.pos_test).float()
        self.pattern_test = torch.from_numpy(self.pattern_test).float()

    def convert_to_numpy(self):
        self.X_train = self.X_train.numpy()
        self.X_train_shuffled = self.X_train_shuffled.numpy()
        self.quat_train = self.quat_train.numpy()
        self.pos_train = self.pos_train.numpy()
        self.pattern_train = self.pattern_train.numpy()

        self.X_test = self.X_test.numpy()
        self.X_test_shuffled = self.X_test_shuffled.numpy()
        self.quat_test = self.quat_test.numpy()
        self.pos_test = self.pos_test.numpy()
        self.pattern_test = self.pattern_test.numpy()


class HyperParams():
    def __init__(self, n_train, n_test, T, batch_size, optimizer, learning_rate, dropout_rate, batch_norm_type, loss_type, comments):
        self.batch_size = batch_size
        self.n_train = n_test
        self.n_test = n_test
        self.T = T
        self.optimizer = optimizer
        self.learning_rate = learning_rate
        self.dropout_rate = dropout_rate
        self.batch_norm_type = batch_norm_type
        self.loss_type = loss_type
        self.comments = comments


class TrainingLog():
    def __init__(self, name, task, model, hyper_params):
        self.name = name
        self.task = task
        self.model = model
        self.hyper_params = hyper_params

        self.train_pose_loss = []
        self.train_quat_loss = []
        self.train_pos_loss = []
        self.test_pose_loss = []
        self.test_quat_loss = []
        self.test_pos_loss = []

    def log_epoch(self, train_pose, train_quat, train_pos, test_pose, test_quat, test_pos):
        self.train_pose_loss.append(train_pose)
        self.train_quat_loss.append(train_quat)
        self.train_pos_loss.append(train_pos)
        self.test_pose_loss.append(test_pose)
        self.test_quat_loss.append(test_quat)
        self.test_quat_loss.append(test_quat)
        self.test_pos_loss.append(test_pos)

    #def save_log(model, hyperparams):
        # folder_name = self.name + '_' + self.task
        # TODO create folder with the following contens:
        # TODO save model, e.g. with torch method
        # TODO save hyper params text file
        #   - write hyperparams to tile
        #   - write best loss values to file
        #   -

        # TODO save training progress, e.g. save numpy with 6 columns


def gen_pattern_constant(N):
    marker1 = np.array([0, 0, 0])
    marker2 = np.array([0, 0, 0.5])
    marker3 = np.array([-0.7, -1, 0])
    marker4 = np.array([1.1, -1, 0.8])

    pattern = np.stack([marker1, marker2, marker3, marker4], axis=0)

    stacked_marker1 = np.tile(marker1, reps=(T, N, 1))
    stacked_marker2 = np.tile(marker2, reps=(T, N, 1))
    stacked_marker3 = np.tile(marker3, reps=(T, N, 1))
    stacked_marker4 = np.tile(marker4, reps=(T, N, 1))

    pattern = np.stack([stacked_marker1, stacked_marker2, stacked_marker3, stacked_marker4], axis=2)

    #stacked_marker1 = torch.from_numpy(stacked_marker1).float()
    #stacked_marker2 = torch.from_numpy(stacked_marker2).float()
    #stacked_marker3 = torch.from_numpy(stacked_marker3).float()
    #stacked_marker4 = torch.from_numpy(stacked_marker4).float()

    return pattern, stacked_marker1, stacked_marker2, stacked_marker3, stacked_marker4


def gen_pattern(N):

    # one marker is always the origin
    marker1 = np.zeros([T, N, 3])

    # The others have to be generated such that they span a 3-dim space
    marker2 = np.random.uniform(-1, 1, [1, N, 3])

    marker3 = np.random.uniform(-1, 1, [1, N, 3])
    ortho_marker2 = np.stack([marker2[:,:,1] + marker2[:, :, 2], -marker2[:, :, 0], -marker2[:, :, 0]], axis=2)
    marker3 = (marker3 + ortho_marker2) / 2

    ortho_marker23 = np.cross(marker2, marker3)
    scale_marker2 = np.random.uniform(-1, 1, [1, N, 1])
    scale_marker3 = np.random.uniform(-1, 1, [1, N, 1])
    scale_ortho = np.random.uniform(0.1, 1, [1, N, 1]) * np.random.choice([-1, 1], size=[1, N, 1], replace=True)
    marker4 = scale_marker2 * marker2 + scale_marker3 + marker3 + scale_ortho * ortho_marker23

    marker2 = np.tile(marker2/10, [T, 1, 1])
    marker3 = np.tile(marker3/10, [T, 1, 1])
    marker4 = np.tile(marker4/10, [T, 1, 1])

    pattern = np.stack([marker1, marker2, marker3, marker4], axis=2)

    return pattern, marker1, marker2, marker3, marker4


def gen_quats(length):
    theta_range = np.random.uniform(1,2)
    theta = np.linspace(-theta_range * np.pi, theta_range * np.pi, length)
    z_range = np.random.randint(1,10)
    z = np.random.uniform(1,3)*np.sin(np.linspace(0, z_range, length))
    rx = np.abs(z) ** np.random.uniform(1.5,3)*np.abs(np.random.rand())  + 1
    ry = np.abs(z) ** np.random.uniform(1.5,3)*np.abs(np.random.rand())  + 1
    x = rx**1.5 * np.sin(theta)
    y = ry**1.5 * np.cos(theta)
    w = 1 + np.random.uniform(0.5, 4)*np.sin(theta)*np.cos(theta)**2
    quats = np.stack([w, x, y, z], axis=1)
    quats = quats / np.expand_dims(np.sqrt(np.sum(np.square(quats), axis=1)), axis=1)
    #quats = np.tile(np.array([1, 0, 0, 0]), [length, 1])
    return quats


def Gen_Spirals(length, dims=2):
    theta_range = np.random.randint(1,10)
    theta = np.linspace(-theta_range * np.pi, theta_range * np.pi, length)
    z_range = np.random.randint(15,45)
    z = np.random.uniform(1,3)*np.sin(np.linspace(0, z_range, length))
    rx = np.abs(z) ** np.random.uniform(1.5,3)*np.abs(np.random.rand())  + 1
    ry = np.abs(z) ** np.random.uniform(1.5,3)*np.abs(np.random.rand())  + 1
    x = rx**1.5 * np.sin(theta)
    y = ry**1.5 * np.cos(theta)

    return np.stack([x,y,z], axis=1) + 5*np.random.uniform(low=-5, high=5, size=[1,dims])


def scale_trajectory(trajectory):
    max_pos = np.max(trajectory, axis=0)
    min_pos = np.min(trajectory, axis=0)
    movement_range = max_pos - min_pos
    return  5 * (trajectory / movement_range)


def center_trajectory(trajectory):
    center = np.mean(trajectory, axis=0)
    return trajectory - center


def gen_pos(N):

    pos = np.zeros([T, N, 3], dtype=np.float32)

    for n in range(N):
        trajectory = Gen_Spirals(T, 3)
        trajectory = center_trajectory(trajectory)
        trajectory = scale_trajectory(trajectory)
        pos[:, n, :] = trajectory

    return pos


def qrot(q, v):
    #TODO can I change this function to also work with constant v and changing quaternions?
    # if not just tile/stack v accordingly
    """
    Rotate vector(s) v about the rotation described by quaternion(s) q.
    Expects a tensor of shape (*, 4) for q and a tensor of shape (*, 3) for v,
    where * denotes any number of dimensions.
    Returns a tensor of shape (*, 3).+

    source: https://github.com/facebookresearch/QuaterNet/blob/master/common/quaternion.py
    """
    assert q.shape[-1] == 4
    assert v.shape[-1] == 3
    if not q.shape[:-1] == v.shape[:-1]:
        q_batch_size = list(q.shape)[1]
        size = int(q_batch_size/BATCH_SIZE)
        v = v.repeat([1, size, 1])

    original_shape = list(v.shape)
    q = q.view(-1, 4)
    v = v.view(-1, 3)

    qvec = q[:, 1:]
    uv = torch.cross(qvec, v, dim=1)
    uuv = torch.cross(qvec, uv, dim=1)
    return (v + 2 * (q[:, :1] * uv + uuv)).view(original_shape)


# TODO: vecotrize with qrot() and by shuffling markers while generating them
def gen_training_data(N_train, N_test):

    quat_train = np.zeros([T, N_train, 4], dtype=np.float32)
    quat_test = np.zeros([T, N_test, 4], dtype=np.float32)

    for n in range(N_train):
        quat_train[:, n, :] = gen_quats(T)

    for n in range(N_test):
        quat_test[:, n, :] = gen_quats(T)

    pos_train = gen_pos(N_train)
    pos_test = gen_pos(N_test)

    pos_train_stacked = np.tile(pos_train, [1, 1, 4])
    pos_test_stacked = np.tile(pos_test, [1, 1, 4])

    if use_const_pat:
        pattern_train, _, _, _, _ = gen_pattern_constant(N_train)
        pattern_test, _, _, _, _ = gen_pattern_constant(N_test)
    else:
        pattern_train, _, _, _, _ = gen_pattern(N_train)
        pattern_test, _, _, _, _ = gen_pattern(N_test)

    X_train = np.zeros([T, N_train, 12])
    X_train_shuffled = np.zeros([T, N_train, 12])
    X_test = np.zeros([T, N_test, 12])
    X_test_shuffled = np.zeros([T, N_test, 12])

    for t in range(T):
        for n in range(N_train):
            p_train = pattern_train[t, n, :, :]
            p_train_copy = np.copy(p_train)

            q = Quaternion(quat_train[t, n, :])
            np.random.shuffle(p_train_copy)
            rotated_pattern = (q.rotation_matrix @ p_train_copy.T).T
            if drop_some_dets and np.random.uniform(0,1) < 0.5:
                rotated_pattern[3,:] = np.array([-1000,-1000,-1000])
                if drop_some_dets and np.random.uniform(0, 1) < 0.5:
                    rotated_pattern[2, :] = np.array([-1000, -1000, -1000])
            X_train_shuffled[t, n, :] = np.reshape(rotated_pattern, -1)

            rotated_pattern = (q.rotation_matrix @ p_train.T).T
            X_train[t, n, :] = np.reshape(rotated_pattern, -1)

    for t in range(T):
        for n in range(N_test):
            p_test = pattern_test[t, n, :, :]
            p_test_copy = np.copy(p_test)

            q = Quaternion(quat_test[t, n, :])
            np.random.shuffle(p_test_copy)
            rotated_pattern = (q.rotation_matrix @ p_test_copy.T).T
            if drop_some_dets and np.random.uniform(0,1) < 0.5:
                rotated_pattern[3,:] = np.array([-1000,-1000,-1000])
                if drop_some_dets and np.random.uniform(0, 1) < 0.5:
                    rotated_pattern[2, :] = np.array([-1000, -1000, -1000])
            X_test_shuffled[t, n, :] = np.reshape(rotated_pattern, -1)

            rotated_pattern = (q.rotation_matrix @ p_test.T).T
            X_test[t, n, :] = np.reshape(rotated_pattern, -1)

    X_train = X_train + pos_train_stacked
    X_train_shuffled = X_train_shuffled + pos_train_stacked
    X_test = X_test + pos_test_stacked
    X_test_shuffled = X_test_shuffled + pos_test_stacked

    data = TrainingData()
    data.set_train_data(X_train, X_train_shuffled, quat_train, pos_train, pattern_train)
    data.set_test_data(X_test, X_test_shuffled, quat_test, pos_test, pattern_test)
    data.save_data(generated_data_dir)
    data.convert_to_torch()

    #maxi1 = max(np.max(quat_train[:, :, 0]), np.max(quat_test[:, :, 0])) / 5
    #maxi2 = max(np.max(quat_train[:, :, 1]), np.max(quat_test[:, :, 1])) / 5
    #maxi3 = max(np.max(quat_train[:, :, 2]), np.max(quat_test[:, :, 2])) / 5
    #maxi4 = max(np.max(quat_train[:, :, 3]), np.max(quat_test[:, :, 3])) / 5

   #quat_train[:, :, 0] = quat_train[:, :, 0]# / maxi1
   #quat_train[:, :, 1] = quat_train[:, :, 1]# / maxi2
   #quat_train[:, :, 2] = quat_train[:, :, 2]# / maxi3
   #quat_train[:, :, 3] = quat_train[:, :, 3]# / maxi4

   #quat_test[:, :, 0] = quat_test[:, :, 0]# / maxi1
   #quat_test[:, :, 1] = quat_test[:, :, 1]# / maxi2
   #quat_test[:, :, 2] = quat_test[:, :, 2]# / maxi3
   #quat_test[:, :, 3] = quat_test[:, :, 3]# / maxi4

   #stacked_marker1 = np.tile(marker1, reps=(T, N, 1))
   #stacked_marker2 = np.tile(marker2, reps=(T, N, 1))
   #stacked_marker3 = np.tile(marker3, reps=(T, N, 1))
   #stacked_marker4 = np.tile(marker4, reps=(T, N, 1))




   ##print(np.shape(stacked_marker1))
   ##print(np.shape(quat_train))
   #assert np.shape(stacked_marker1)[:2] == np.shape(quat_train)[:2]

   #stacked_marker1 = torch.from_numpy(stacked_marker1).float()
   #stacked_marker2 = torch.from_numpy(stacked_marker2).float()
   #stacked_marker3 = torch.from_numpy(stacked_marker3).float()
   #stacked_marker4 = torch.from_numpy(stacked_marker4).float()

   #quat_train = torch.from_numpy(quat_train).float()
   #quat_test = torch.from_numpy(quat_test).float()

   #rotated_marker1_train = qrot(quat_train, stacked_marker1)
   #rotated_marker2_train = qrot(quat_train, stacked_marker2)
   #rotated_marker3_train = qrot(quat_train, stacked_marker3)
   #rotated_marker4_train = qrot(quat_train, stacked_marker4)
   #X_train = torch.cat([rotated_marker1_train,
   #                    rotated_marker2_train,
   #                    rotated_marker3_train,
   #                    rotated_marker4_train], dim=2)

   #rotated_marker1_test = qrot(quat_test, stacked_marker1)
   #rotated_marker2_test = qrot(quat_test, stacked_marker2)
   #rotated_marker3_test = qrot(quat_test, stacked_marker3)
   #rotated_marker4_test = qrot(quat_test, stacked_marker4)
   #X_test = torch.cat( [rotated_marker1_test,
   #                    rotated_marker2_test,
   #                    rotated_marker3_test,
   #                    rotated_marker4_test], dim=2)
   #

    return data


def load_training_data():
    data = TrainingData()
    data.load_data(generated_data_dir)
    global T, N_train, N_eval
    T = np.shape(data.X_train)[0]
    N_train = np.shape(data.X_train)[1]
    N_eval = np.shape(data.X_test)[1]
    data.convert_to_torch()
    return data


# todo custom LSTM-cell
class LSTMTracker(nn.Module):

    def __init__(self, hidden_dim):
        super(LSTMTracker, self).__init__()
        self.hidden_dim = hidden_dim

        self.fc1_det = nn.Linear(12, fc1_det_dim)
        self.fc2_det = nn.Linear(fc1_det_dim, fc2_det_dim)
        self.fc3_det = nn.Linear(fc2_det_dim, fc3_det_dim)
        self.fc4_det = nn.Linear(fc3_det_dim, fc4_det_dim)

        if not use_const_pat:
            self.fc1_pat = nn.Linear(12, fc1_pat_dim)
            self.fc2_pat = nn.Linear(fc1_pat_dim, fc2_pat_dim)
            self.fc3_pat = nn.Linear(fc2_pat_dim, fc3_pat_dim)

        #self.fc1_combo = nn.Linear(fc2_pat_dim + fc3_det_dim, fc1_combo_dim)
        #self.fc2_combo = nn.Linear(fc1_combo_dim, fc2_combo_dim)

        if use_const_pat:
            self.lstm = nn.LSTM(fc4_det_dim, hidden_dim)
        else:
            self.lstm = nn.LSTM(fc4_det_dim + fc3_pat_dim, hidden_dim)

        # The linear layer that maps from hidden state space to tag space
        self.hidden2quat1 = nn.Linear(hidden_dim, fc_out_1_size)
        self.hidden2quat2 = nn.Linear(fc_out_1_size, 4)

        self.hidden2pos = nn.Linear(hidden_dim, 3)

        self.dropout = nn.Dropout(p=DROPOUT_RATE)

    def forward(self, detections, patterns):
        marker1 = patterns[:, :, 0, :].contiguous()
        marker2 = patterns[:, :, 1, :].contiguous()
        marker3 = patterns[:, :, 2, :].contiguous()
        marker4 = patterns[:, :, 3, :].contiguous()

        x = self.dropout(F.relu(self.fc1_det(detections)))
        x = self.dropout(F.relu(self.fc2_det(x)))
        x = self.dropout(F.relu(self.fc3_det(x)))
        x = self.dropout(F.relu(self.fc4_det(x)))

        if not use_const_pat:
            x_pat = self.dropout(F.relu(self.fc1_pat(patterns.view(T-1, -1, 12))))
            x_pat = self.dropout(F.relu(self.fc2_pat(x_pat)))
            x_pat = self.dropout(F.relu(self.fc3_pat(x_pat)))
            x = torch.cat([x, x_pat], dim=2)

        #x_combo = self.dropout(F.relu(self.fc1_combo(x_combo)))
        #x_combo = self.dropout(F.relu(self.fc2_combo(x_combo)))

        #x = torch.cat([x_det, x_pat], dim=2)

        #x = x_det - x_pat

        lstm_out, _ = self.lstm(x)
        x = F.relu(self.hidden2quat1(lstm_out))
        quat_space = self.hidden2quat2(x)
        pos_space = self.hidden2pos(lstm_out)
        # maybe leave out wenn not using pose error
        quat_norm = torch.sqrt(torch.sum(torch.pow(quat_space, 2, ), dim=2))
        quat_space = quat_space / torch.unsqueeze(quat_norm, dim=2)

        rotated_marker1 = qrot(quat_space, marker1) + pos_space
        rotated_marker2 = qrot(quat_space, marker2) + pos_space
        rotated_marker3 = qrot(quat_space, marker3) + pos_space
        rotated_marker4 = qrot(quat_space, marker4) + pos_space
        rotated_pattern = torch.cat([rotated_marker1,
                                     rotated_marker2,
                                     rotated_marker3,
                                     rotated_marker4], dim=2)

        return quat_space, pos_space, rotated_pattern

model = LSTMTracker(hidden_dim)

# TODO determine automatically from model
hyper_params = HyperParams(N_train, N_eval, T, BATCH_SIZE, 'ADAM', LEARNING_RATE, DROPOUT_RATE, 'NONE', 'l2 on pos + 5* l1 on quat', '')


# TODO: try pose error!!
# TODO: respect antipodal pair as well!
loss_function_pose = nn.MSELoss() #nn.L1Loss() #nn.MSELoss()
loss_function_quat = nn.L1Loss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)


def train():
    #TODO: store patterns
    #TODO: adapt architecture to acceot patterns as well
    data = gen_training_data(N_train, N_eval)

    for gci in range(10):
        gc.collect()

    model.train()

    for epoch in range(NUM_EPOCHS):
        batches = torch.split(data.X_train_shuffled, BATCH_SIZE, 1)
        quat_truth_batches = torch.split(data.quat_train, BATCH_SIZE, 1)
        pos_truth_batches = torch.split(data.pos_train, BATCH_SIZE, 1)
        batches_not_shuffled = torch.split(data.X_train, BATCH_SIZE, 1)
        pattern_batches = torch.split(data.pattern_train, BATCH_SIZE, 1)
        avg_loss_pose = 0
        avg_loss_quat = 0
        avg_loss_pos = 0
        for batch, quat_truth_batch, pos_truth_batch, batch_not_shuffled, pattern_batch in zip(batches, quat_truth_batches, pos_truth_batches, batches_not_shuffled, pattern_batches):
            model.zero_grad()

            pred_quat, pred_pos, pred_markers = model(batch[:-1, :, :], pattern_batch[:-1, :, :, :])

            loss_pose = loss_function_pose(pred_markers, batch_not_shuffled[1:, :, :])
            loss_quat = loss_function_quat(pred_quat, quat_truth_batch[1:, :, :])
            loss_pos = loss_function_pose(pred_pos, pos_truth_batch[1:, :, :])

            loss = loss_pos + loss_quat #loss_pose + 10*loss_quat #+ loss_pos
            loss.backward()
            optimizer.step()
            avg_loss_pose += loss_pose
            avg_loss_quat += loss_quat
            avg_loss_pos += loss_pos
        avg_loss_pose /= len(batches)
        avg_loss_quat /= len(batches)
        avg_loss_pos /= len(batches)

        model.eval()
        with torch.no_grad():
            pred_quat, pred_pos, preds  = model(data.X_test_shuffled[:-1,:,:], data.pattern_test[:-1, :, :, :])
            loss_pose = loss_function_pose(preds, data.X_test[1:,:,:])
            loss_quat = loss_function_quat(pred_quat, data.quat_test[1:, :, :])
            loss_pos = loss_function_pose(pred_pos, data.pos_test[1:, :, :])
            print("TrainPoseLoss: {train_pose:2.4f}, TrainQuatLoss: {train_quat:2.4f}  TrainPosLoss: {train_pos:2.4f}\t TestPoseLoss: {test_pose:2.4f}, TestQuatLoss: {test_quat:2.4f}, TestPosLoss: {test_pos:2.4f}".format(
                train_pose=avg_loss_pose.data, train_quat=avg_loss_quat.data, train_pos=avg_loss_pos.data, test_pose=loss_pose, test_quat=loss_quat, test_pos=loss_pos.data))
    torch.save(model.state_dict(), weight_file)


def eval():
    data = gen_training_data(10, N_eval)

    model.load_state_dict(torch.load(weight_file))
    model.eval()


    with torch.no_grad():
        quat_preds, pos_preds, _ = model(data.X_test[:-1, :, :], data.pattern_test[:-1, :, :])

        for n in range(10):
            visualize_tracking(pos_preds[:, n, :].detach().numpy(),
                               quat_preds[:, n, :].detach().numpy(),
                               data.pos_test[1:, n, :].detach().numpy(),
                               data.quat_test[1:, n, :].detach().numpy(),
                               data.X_test_shuffled[:-1, n, :].numpy(),
                               data.pattern_test[0, n, :].numpy())



#

train()
eval()