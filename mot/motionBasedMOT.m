%% Motion-Based Multiple Object Tracking
% This example shows how to perform automatic detection and motion-based
% tracking of moving objects in a video from a stationary camera.
%
%   Copyright 2014 The MathWorks, Inc.

%%
% Detection of moving objects and motion-based tracking are important 
% components of many computer vision applications, including activity
% recognition, traffic monitoring, and automotive safety.  The problem of
% motion-based object tracking can be divided into two parts:
%
% # Detecting moving objects in each frame 
% # Associating the detections corresponding to the same object over time
%
% The detection of moving objects uses a background subtraction algorithm
% based on Gaussian mixture models. Morphological operations are applied to
% the resulting foreground mask to eliminate noise. Finally, blob analysis
% detects groups of connected pixels, which are likely to correspond to
% moving objects. 
%
% The association of detections to the same object is based solely on
% motion. The motion of each track is estimated by a Kalman filter. The
% filter is used to predict the track's location in each frame, and
% determine the likelihood of each detection being assigned to each 
% track.
%
% Track maintenance becomes an important aspect of this example. In any
% given frame, some detections may be assigned to tracks, while other
% detections and tracks may remain unassigned. The assigned tracks are
% updated using the corresponding detections. The unassigned tracks are 
% marked invisible. An unassigned detection begins a new track. 
%
% Each track keeps count of the number of consecutive frames, where it
% remained unassigned. If the count exceeds a specified threshold, the
% example assumes that the object left the field of view and it deletes the
% track.  
%
% For more information please see
% <matlab:helpview(fullfile(docroot,'toolbox','vision','vision.map'),'multipleObjectTracking') Multiple Object Tracking>.
%
% This example is a function with the main body at the top and helper 
% routines in the form of 
% <matlab:helpview(fullfile(docroot,'toolbox','matlab','matlab_prog','matlab_prog.map'),'nested_functions') nested functions> 
% below.

function motionBasedMOT(D, D_clustered)

% Create System objects used for reading video, detecting moving objects,
% and displaying the results.

%%%%%%%%TODO%%%%%%%%
% manually LOAD DATA
[N,C] = size(D);
K = C / 7;
X = zeros(N, K);
Y = zeros(N, K);
Z = zeros(N, K);
column_idx = 1;
for c = 1:70
    if mod(c,7) == 5
        X(:,column_idx) = D(:,c); 
    elseif mod(c,7) == 6
        Y(:,column_idx) = D(:,c); 
    elseif mod(c,7) == 0
        Z(:,column_idx) = D(:,c); 
        column_idx = column_idx + 1;
    end
end

% Get extreme coordinates
X_min = min(X, [], 'all');
X_max = max(X, [], 'all');
Y_min = min(Y, [], 'all');
Y_max = max(Y, [], 'all');
Z_min = min(Z, [], 'all');
Z_max = max(Z, [], 'all');
%%%%%%%%TODO%%%%%%%%

tracks = initializeTracks(); % Create an empty array of tracks.
P = cell(15,1);
initializeFigure();
nextId = 1; % ID of the next track

% Detect moving objects, and track them across video frames.
for t = 1:N
    frame_X = X(t,:);
    frame_Y = Y(t,:);
    frame_Z = Z(t,:);

    detections = cat(2, frame_X(~isnan(frame_X))', frame_Y(~isnan(frame_Y))', frame_Z(~isnan(frame_Z))');
    
    % Also include non-assigned detections
    clusters = process_clusters(D_clustered(t,:));
    detections = combine_detections(detections, clusters);
    predictNewLocationsOfTracks();
    [assignments, unassignedTracks, unassignedDetections] = ...
        detectionToTrackAssignment();
    
    updateAssignedTracks();
    updateUnassignedTracks();
    deleteLostTracks();
    createNewTracks();
    
    displayTrackingResults();
end


%% Initialize Tracks
% The |initializeTracks| function creates an array of tracks, where each
% track is a structure representing a moving object in the video. The
% purpose of the structure is to maintain the state of a tracked object.
% The state consists of information used for detection to track assignment,
% track termination, and display. 
%
% The structure contains the following fields:
%
% * |id| :                  the integer ID of the track
% * |bbox| :                the current bounding box of the object; used
%                           for display
% * |kalmanFilter| :        a Kalman filter object used for motion-based
%                           tracking
% * |age| :                 the number of frames since the track was first
%                           detected
% * |totalVisibleCount| :   the total number of frames in which the track
%                           was detected (visible)
% * |consecutiveInvisibleCount| : the number of consecutive frames for 
%                                  which the track was not detected (invisible).
%
% Noisy detections tend to result in short-lived tracks. For this reason,
% the example only displays an object after it was tracked for some number
% of frames. This happens when |totalVisibleCount| exceeds a specified 
% threshold.    
%
% When no detections are associated with a track for several consecutive
% frames, the example assumes that the object has left the field of view 
% and deletes the track. This happens when |consecutiveInvisibleCount|
% exceeds a specified threshold. A track may also get deleted as noise if 
% it was tracked for a short time, and marked invisible for most of the 
% frames.        

    function tracks = initializeTracks()
        % create an empty array of tracks
        tracks = struct(...
            'id', {}, ...
            'center', {}, ...
            'kalmanFilter', {}, ...
            'age', {}, ...
            'totalVisibleCount', {}, ...
            'consecutiveInvisibleCount', {});
    end

%% Predict New Locations of Existing Tracks
% Use the Kalman filter to predict the centroid of each track in the
% current frame, and update its bounding box accordingly.

    function predictNewLocationsOfTracks()
        for i = 1:length(tracks)  
            % Predict the current location of the track.
            tracks(i).center = predict(tracks(i).kalmanFilter);
        end
    end

%% Assign Detections to Tracks
% Assigning object detections in the current frame to existing tracks is
% done by minimizing cost. The cost is defined as the negative
% log-likelihood of a detection corresponding to a track.  
%
% The algorithm involves two steps: 
%
% Step 1: Compute the cost of assigning every detection to each track using
% the |distance| method of the |vision.KalmanFilter| System object(TM). The 
% cost takes into account the Euclidean distance between the predicted
% centroid of the track and the centroid of the detection. It also includes
% the confidence of the prediction, which is maintained by the Kalman
% filter. The results are stored in an MxN matrix, where M is the number of
% tracks, and N is the number of detections.   
%
% Step 2: Solve the assignment problem represented by the cost matrix using
% the |assignDetectionsToTracks| function. The function takes the cost 
% matrix and the cost of not assigning any detections to a track.  
%
% The value for the cost of not assigning a detection to a track depends on
% the range of values returned by the |distance| method of the 
% |vision.KalmanFilter|. This value must be tuned experimentally. Setting 
% it too low increases the likelihood of creating a new track, and may
% result in track fragmentation. Setting it too high may result in a single 
% track corresponding to a series of separate moving objects.   
%
% The |assignDetectionsToTracks| function uses the Munkres' version of the
% Hungarian algorithm to compute an assignment which minimizes the total
% cost. It returns an M x 2 matrix containing the corresponding indices of
% assigned tracks and detections in its two columns. It also returns the
% indices of tracks and detections that remained unassigned. 

    function [assignments, unassignedTracks, unassignedDetections] = ...
            detectionToTrackAssignment()
        
        nTracks = length(tracks);
        nDetections = size(detections, 1);
        
        % Compute the cost of assigning each detection to each track.
        cost = zeros(nTracks, nDetections);
        for i = 1:nTracks
            cost(i, :) = distance(tracks(i).kalmanFilter, detections);
        end
        
        % Solve the assignment problem.
        costOfNonAssignment = 300;
        [assignments, unassignedTracks, unassignedDetections] = ...
            assignDetectionsToTracks(cost, costOfNonAssignment);
    end

%% Update Assigned Tracks
% The |updateAssignedTracks| function updates each assigned track with the
% corresponding detection. It calls the |correct| method of
% |vision.KalmanFilter| to correct the location estimate. Next, it stores
% the new bounding box, and increases the age of the track and the total
% visible count by 1. Finally, the function sets the invisible count to 0. 

    function updateAssignedTracks()
        nAssignedTracks = size(assignments, 1);
        for i = 1:nAssignedTracks
            trackIdx = assignments(i, 1);
            detectionIdx = assignments(i, 2);
            center = detections(detectionIdx, :);
            
            % Correct the estimate of the object's location
            % using the new detection.
            correct(tracks(trackIdx).kalmanFilter, center);
            
            % Replace predicted bounding box with detected
            % bounding box.
            tracks(trackIdx).center = center;
            
            % Update track's age.
            tracks(trackIdx).age = tracks(trackIdx).age + 1;
            
            % Update visibility.
            tracks(trackIdx).totalVisibleCount = ...
                tracks(trackIdx).totalVisibleCount + 1;
            tracks(trackIdx).consecutiveInvisibleCount = 0;
        end
    end

%% Update Unassigned Tracks
% Mark each unassigned track as invisible, and increase its age by 1.

    function updateUnassignedTracks()
        for i = 1:length(unassignedTracks)
            ind = unassignedTracks(i);
            tracks(ind).age = tracks(ind).age + 1;
            tracks(ind).consecutiveInvisibleCount = ...
                tracks(ind).consecutiveInvisibleCount + 1;
        end
    end

%% Delete Lost Tracks
% The |deleteLostTracks| function deletes tracks that have been invisible
% for too many consecutive frames. It also deletes recently created tracks
% that have been invisible for too many frames overall. 

    function deleteLostTracks()
        if isempty(tracks)
            return;
        end
        
        invisibleForTooLong = 150;
        ageThreshold = 5;
        
        % Compute the fraction of the track's age for which it was visible.
        ages = [tracks(:).age];
        totalVisibleCounts = [tracks(:).totalVisibleCount];
        visibility = totalVisibleCounts ./ ages;
        
        % Find the indices of 'lost' tracks.
        lostInds = (ages < ageThreshold & visibility < 0.6) | ...
            [tracks(:).consecutiveInvisibleCount] >= invisibleForTooLong;
        
        % Delete lost tracks.
        tracks = tracks(~lostInds);
    end

%% Create New Tracks
% Create new tracks from unassigned detections. Assume that any unassigned
% detection is a start of a new track. In practice, you can use other cues
% to eliminate noisy detections, such as size, location, or appearance.

    function createNewTracks()
        centers = detections(unassignedDetections, :);
        
        for i = 1:size(centers, 1)
            
            center = centers(i,:);
            
            % Create a Kalman filter object.
            kalmanFilter = configureKalmanFilter('ConstantVelocity', ...
                center, [100, 40], [100, 70], 100);
            
            % Create a new track.
            newTrack = struct(...
                'id', nextId, ...
                'center', center, ...
                'kalmanFilter', kalmanFilter, ...
                'age', 1, ...
                'totalVisibleCount', 1, ...
                'consecutiveInvisibleCount', 0);
            
            % Add it to the array of tracks.
            tracks(end + 1) = newTrack;
            
            % Increment the next id.
            nextId = nextId + 1;
        end
    end

%% Display Tracking Results
% The |displayTrackingResults| function draws a bounding box and label ID 
% for each track on the video frame and the foreground mask. It then 
% displays the frame and the mask in their respective video players. 

    function initializeFigure()
        scatter3([X_min, X_max], [Y_min, Y_max], [Z_min, Z_max], '*')
        hold on;
        for k = 1:15
            %TODO wie geht list richtig?
            if k < 6
                P{k} = plot3(X(1,k),Y(1,k),Z(1,k), 'o', 'MarkerSize', 10);
            elseif k < 11
                P{k} = plot3(X(1,k),Y(1,k),Z(1,k), '+', 'MarkerSize', 10);
            else
                P{k} = plot3(NaN,NaN,NaN, '*', 'MarkerSize', 10);
            end
        end
        grid on;
        hold off
        axis manual
    end

    function displayTrackingResults()
        for k = 1:15
            if k <= length(tracks)
                if tracks(k).totalVisibleCount < 5
                    continue;
                else
                    center = tracks(k).center;
                    P{k}.XData = center(1,1);
                    P{k}.YData = center(1,2);
                    P{k}.ZData = center(1,3);
                end
            else
                P{k}.XData = NaN;
                P{k}.YData = NaN;
                P{k}.ZData = NaN;
            end
        end
        if length(tracks) > 15
            fprintf('Thats a lota tracks')
        end
        drawnow 
    end

%% Summary
% This example created a motion-based system for detecting and
% tracking multiple moving objects. Try using a different video to see if
% you are able to detect and track objects. Try modifying the parameters
% for the detection, assignment, and deletion steps.  
%
% The tracking in this example was solely based on motion with the
% assumption that all objects move in a straight line with constant speed.
% When the motion of an object significantly deviates from this model, the
% example may produce tracking errors. Notice the mistake in tracking the
% person labeled #12, when he is occluded by the tree. 
%
% The likelihood of tracking errors can be reduced by using a more complex
% motion model, such as constant acceleration, or by using multiple Kalman
% filters for every object. Also, you can incorporate other cues for
% associating detections over time, such as size, shape, and color. 

    function cluster_centers = process_clusters(clusters)
        %num_clusters = sum(~cellfun(@isempty,clusters),2);
        num_clusters = 0;
        for k = 1:length(clusters)
            if size(clusters{1,k},1) > 1
                num_clusters = num_clusters + 1;
            end
        end
        
        %TODO viellicht cluster mit size 1 wegnehmen
        %TODO Checken ob vielleicht sogar zu fein geclustert wird, das k�nnte in geschossen reultieren
        
        cluster_centers = zeros(num_clusters,3);
        idx = 1;
        for c = 1:length(clusters)
            if size(clusters{1,c},1) > 1
                cluster_centers(idx,:) = mean(clusters{1,c},1);
                idx = idx + 1;
            end
        end
    end

    function all_detections = combine_detections(assgn, unassgn)
        is_new_detection = false(size(unassgn));
        for i = 1:size(unassgn,1)
           p = unassgn(i,:);
           d = sqrt(sum((assgn - p).^2,2));
           is_new_detection(i) = min(d) > 230;
        end
        all_detections = [assgn;unassgn(is_new_detection,:)];
    end

end