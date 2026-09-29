// Learning goals get an origin: "manual" (typed by the learner) or "roadmap" (a course made from the
// learning roadmap). Goals from before this field are manual.
MATCH (g:LearningGoal) WHERE g.origin IS NULL SET g.origin = 'manual';
