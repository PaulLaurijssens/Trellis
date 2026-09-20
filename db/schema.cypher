// ---- Constraints ----
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT pending_source_id IF NOT EXISTS FOR (p:PendingSource) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT chat_session_id IF NOT EXISTS FOR (s:ChatSession) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;

// ---- Fulltext (naam/alias/definitie zoeken) ----
CREATE FULLTEXT INDEX concept_text IF NOT EXISTS
FOR (c:Concept) ON EACH [c.name, c.aliases, c.definition];

// ---- Vector index (dimensie = embed-model; gemini-embedding-2 default = 3072) ----
CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
FOR (c:Concept) ON (c.embedding)
OPTIONS { indexConfig: { `vector.dimensions`: 3072, `vector.similarity_function`: 'cosine' } };

// ---- Chat (laag 1: ruwe gesprekslog, bron van waarheid) ----
CREATE INDEX chat_session_open IF NOT EXISTS
FOR (s:ChatSession) ON (s.consolidated, s.last_activity);

// ---- Personen ----
MERGE (p:Person {id: 'paul'}) SET p.name = 'Paul', p.level = 5;
MERGE (p:Person {id: 'zoon'}) SET p.name = 'Zoon', p.level = 1;

// Datamodel
// (:Concept {id, name, aliases[], definition, domain, embedding, created_at,
//            status: suggested|learning|learned})
// (:Source  {id, type: youtube|paper|text|manual, title, url, ingested_at})
// (:PendingSource {id, type, title, url, created_at})  // suggestieronde; promoveert bij /learn
// (:Person  {id, name, level 1..5, learning_profile: JSON-string})   // laag 3
// (Concept)-[:PREREQUISITE_OF]->(Concept)
// (Concept)-[:PART_OF]->(Concept)
// (Concept)-[:RELATED_TO {strength}]-(Concept)
// (Concept)-[:MENTIONED_IN {context, importance}]->(Source)
// (Concept)-[:PREREQUISITE_OF {strength, reason}]->(Concept)
// (Person)-[:ASKED_ABOUT {ts}]->(Concept)
// (Person)-[:UNDERSTANDS {level, status, since, last_session,       // laag 2
//            covered[], struggles[], misconceptions[], summary,
//            quiz_correct, quiz_wrong,
//            removed[], manual_fields[]}]->(Concept)
// (:ChatSession {id, person_id, concept_id, level, started_at, last_activity, consolidated})
// (:ChatMessage {seq, role, content, ts})
// (Person)-[:HAD_SESSION]->(ChatSession)-[:ABOUT]->(Concept)
// (ChatSession)-[:HAS_MESSAGE]->(ChatMessage)

// Conversation proposals, isolated until explicit acceptance.
CREATE CONSTRAINT concept_suggestion_id IF NOT EXISTS FOR (s:ConceptSuggestion) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT learning_goal_id IF NOT EXISTS FOR (g:LearningGoal) REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT helpful_example_id IF NOT EXISTS FOR (e:HelpfulExample) REQUIRE e.id IS UNIQUE;

// ---- /teach integration (additive; see docs M0 design §3.2) ----
// Truth lives in these nodes. The Markdown workspace of the teaching agent is a one-way export.
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT topic_objective_id IF NOT EXISTS FOR (o:TopicObjective) REQUIRE o.id IS UNIQUE;
CREATE CONSTRAINT topic_recommendation_id IF NOT EXISTS FOR (r:TopicRecommendation) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT lesson_id IF NOT EXISTS FOR (l:Lesson) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT lesson_version_id IF NOT EXISTS FOR (v:LessonVersion) REQUIRE v.id IS UNIQUE;
CREATE CONSTRAINT lesson_run_id IF NOT EXISTS FOR (r:LessonRun) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT lesson_job_id IF NOT EXISTS FOR (j:LessonJob) REQUIRE j.id IS UNIQUE;
CREATE CONSTRAINT exercise_attempt_id IF NOT EXISTS FOR (a:ExerciseAttempt) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT reference_id IF NOT EXISTS FOR (r:Reference) REQUIRE r.id IS UNIQUE;
// (:Topic {id,title,language,origin,seeded_from_plan_key,created_at})-[:COVERS]->(:Concept)
// (:Person)-[:STUDIES {since,familiarity_self_report,approach,last_time_budget_min,resource_gaps_json}]->(:Topic)
// (:TopicObjective {id,person_id,topic_id,revision,status:active|superseded|proposed|rejected,intent,
//                   objective_markdown,observable_outcomes[],preferred_depth,constraints[],out_of_scope[]})
//     -[:FOR_TOPIC]->(:Topic), -[:SUPERSEDES]->(:TopicObjective), -[:SERVES]->(:LearningGoal)
// (:Lesson)-[:HAS_VERSION]->(:LessonVersion)   // version = immutable; files on the artifact volume
// (:LessonRun)-[:OF_VERSION]->(:LessonVersion) // a run never changes version
// (:ExerciseAttempt)-[:IN_RUN]->(:LessonRun)   // layer 1 for exercises, like :ChatMessage for chat
