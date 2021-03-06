import selfdrive.messaging as messaging
import numpy as np
X_PATH = np.arange(0.0, 50.0)

def model_polyfit(points):
  return np.polyfit(X_PATH, map(float, points), 3)

# lane width http://safety.fhwa.dot.gov/geometric/pubs/mitigationstrategies/chapter3/3_lanewidth.cfm
_LANE_WIDTH_V = np.asarray([3., 3.8])

# break points of speed
_LANE_WIDTH_BP = np.asarray([0., 31.])

def calc_desired_path(l_poly, r_poly, p_poly, l_prob, r_prob, p_prob, speed):
  #*** this function computes the poly for the center of the lane, averaging left and right polys
  lane_width = np.interp(speed, _LANE_WIDTH_BP, _LANE_WIDTH_V)

  # lanes in US are ~3.6m wide
  half_lane_poly = np.array([0., 0., 0., lane_width / 2.])
  if l_prob + r_prob > 0.01:
    c_poly = ((l_poly - half_lane_poly) * l_prob +
              (r_poly + half_lane_poly) * r_prob) / (l_prob + r_prob)
    c_prob = np.sqrt((l_prob**2 + r_prob**2) / 2.)
  else:
    c_poly = np.zeros(4)
    c_prob = 0.

  p_weight = 1. # predicted path weight relatively to the center of the lane
  d_poly =  list((c_poly*c_prob + p_poly*p_prob*p_weight ) / (c_prob + p_prob*p_weight))
  return d_poly, c_poly, c_prob

class PathPlanner(object):
  def __init__(self, model):
    self.model = model
    self.dead = True
    self.d_poly = [0., 0., 0., 0.]
    self.last_model = 0.
    self.logMonoTime = 0
    self.lead_dist, self.lead_prob, self.lead_var = 0, 0, 1

  def update(self, cur_time, v_ego):
    md = messaging.recv_sock(self.model)

    if md is not None:
      self.logMonoTime = md.logMonoTime
      p_poly = model_polyfit(md.model.path.points)       # predicted path
      p_prob = 1.                                        # model does not tell this probability yet, so set to 1 for now
      l_poly = model_polyfit(md.model.leftLane.points)   # left line
      l_prob = md.model.leftLane.prob                    # left line prob
      r_poly = model_polyfit(md.model.rightLane.points)  # right line
      r_prob = md.model.rightLane.prob                   # right line prob

      self.lead_dist = md.model.lead.dist
      self.lead_prob = md.model.lead.prob
      self.lead_var = md.model.lead.std**2

      #*** compute target path ***
      self.d_poly, _, _ = calc_desired_path(l_poly, r_poly, p_poly, l_prob, r_prob, p_prob, v_ego)

      self.last_model = cur_time
      self.dead = False
    elif cur_time - self.last_model > 0.5:
      self.dead = True
