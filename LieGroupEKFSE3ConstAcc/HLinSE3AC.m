function J = HLinSE3AC(m1,m2,m3,mu1,mu2,mu3,mu5,mu6,mu7,mu9,mu10,mu11, motionModel)
%HLINSE3AC
%    J = HLINSE3AC(M1,M2,M3,MU1,MU2,MU3,MU5,MU6,MU7,MU9,MU10,MU11)

%    This function was generated by the Symbolic Math Toolbox version 8.2.
%    31-Jan-2020 22:45:33

%J = reshape([m2.*mu3-m3.*mu2, m2.*mu7-m3.*mu6, m2.*mu11-m3.*mu10 ,0.0, -m1.*mu3+m3.*mu1, -m1.*mu7+m3.*mu5, -m1.*mu11+m3.*mu9,0.0,m1.*mu2-m2.*mu1,m1.*mu6-m2.*mu5,m1.*mu10-m2.*mu9,0.0,mu1,mu5,mu9,0.0,mu2,mu6,mu10,0.0,mu3,mu7,mu11,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],[4,12]);

if motionModel == 0
     J = [m2*mu3 - m3*mu2,   m3*mu1 - m1*mu3,  m1*mu2 - m2*mu1,  mu1,  mu2,  mu3;
          m2*mu7 - m3*mu6,   m3*mu5 - m1*mu7,  m1*mu6 - m2*mu5,  mu5,  mu6,  mu7;
          m2*mu11 - m3*mu10, m3*mu9 - m1*mu11, m1*mu10 - m2*mu9, mu9,  mu10, mu11;
          0,                 0,                0,                0,    0,    0];
elseif motionModel == 1
     J = [m2*mu3 - m3*mu2,   m3*mu1 - m1*mu3,  m1*mu2 - m2*mu1,  mu1,  mu2,  mu3,  0, 0, 0, ;
          m2*mu7 - m3*mu6,   m3*mu5 - m1*mu7,  m1*mu6 - m2*mu5,  mu5,  mu6,  mu7,  0, 0, 0, ;
          m2*mu11 - m3*mu10, m3*mu9 - m1*mu11, m1*mu10 - m2*mu9, mu9,  mu10, mu11, 0, 0, 0, ;
          0,                 0,                0,                0,    0,    0,    0, 0, 0, ];
elseif motionModel == 2
    J = [m2*mu3 - m3*mu2,   m3*mu1 - m1*mu3,  m1*mu2 - m2*mu1,  mu1,  mu2,  mu3,  0, 0, 0, 0, 0, 0;
         m2*mu7 - m3*mu6,   m3*mu5 - m1*mu7,  m1*mu6 - m2*mu5,  mu5,  mu6,  mu7,  0, 0, 0, 0, 0, 0;
         m2*mu11 - m3*mu10, m3*mu9 - m1*mu11, m1*mu10 - m2*mu9, mu9,  mu10, mu11, 0, 0, 0, 0, 0, 0;
         0,                 0,                0,                0,    0,    0,    0, 0, 0, 0, 0, 0];
else
   'h() linearized: unexpected motion model' 
end
