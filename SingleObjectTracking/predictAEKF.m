function s = predictAEKF(s)
%PREDICTKALMAN Summary of this function goes here
%   Detailed explanation goes here

        
% Prediction for state vector and covariance:
s.x(s.qIdx) = s.normQ;
s.x = s.A*s.x;
%TODO: so far only brownian motion model for quaternions supported
s.P = s.A * s.P * s.A' + s.Q;

% Predict delta q
s.deltaQ = s.oldQ * s.oldQ' * s.deltaQ;
s.oldQ = s.x(s.qIdx);

        


