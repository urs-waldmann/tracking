function X = vecToSO3Algebra(v)
%VEC2LIEALGEBRA Summary of this function goes here
%   Detailed explanation goes here
X = [0 -v(3) v(2); v(3) 0 -v(1); -v(2) v(1) 0];
end

