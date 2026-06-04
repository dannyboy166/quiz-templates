-- Browse DanTest Data
-- Press Cmd+Shift+E to run each query (select the query first)

-- 1. Overview: How many of each template?
SELECT qt.TemplateName, COUNT(*) as Count
FROM DanTest.Question q
JOIN DanTest.QuestionTemplate qt ON q.TemplateID = qt.QuestionTemplateID
GROUP BY qt.TemplateName
ORDER BY Count DESC;

-- 2. Sample Select One question with answers
SELECT TOP 1 q.QuestionID, q.TextHTML as Question, qt.TemplateName
FROM DanTest.Question q
JOIN DanTest.QuestionTemplate qt ON q.TemplateID = qt.QuestionTemplateID
WHERE q.TemplateID = 1;

-- 3. Sample Select All (multi-answer) question
SELECT TOP 1 q.QuestionID, q.TextHTML as Question
FROM DanTest.Question q
WHERE q.TemplateID = 2;

-- 4. Questions with images
SELECT TOP 10 q.QuestionID, q.TextHTML, b.Filename as ImageFile
FROM DanTest.Question q
JOIN DanTest.Blob b ON q.ImageBlobID = b.BlobID;

-- 5. All subjects
SELECT * FROM DanTest.Subject;

-- 6. Total counts
SELECT
    (SELECT COUNT(*) FROM DanTest.Question) as Questions,
    (SELECT COUNT(*) FROM DanTest.SelectionOption) as Options,
    (SELECT COUNT(*) FROM DanTest.HintReplacement) as Hints,
    (SELECT COUNT(*) FROM DanTest.Blob) as Blobs;
