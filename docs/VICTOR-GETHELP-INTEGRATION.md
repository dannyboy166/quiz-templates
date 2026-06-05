# Get Help Integration Guide

## Demo Links

Two proof-of-concept help lessons:

- **Partitioning Numbers (9 scenes):** https://dannyboy166.github.io/quiz-templates/help/partitioning/
- **Addition (10 scenes):** https://dannyboy166.github.io/quiz-templates/help/addition/

Click the button to play. Deep-link to a specific scene with `?scene=3` etc.

## What Each Lesson Is

- **One self-contained HTML file** per topic (e.g., `addition.html`, `partitioning.html`)
- Multiple **scenes/chapters** inside — one per question sub-skill
- Teacher voiceover (ElevenLabs) synced to animated HTML/CSS/JS visuals
- Scene navigation tabs, seekable progress bar, replay, auto-advance
- **No external dependencies** — all inline CSS/JS, audio via `<audio>` tags
- ~28 files for all Stage 1 Maths topics

## How to Integrate

### Step 1: Upload files to blob storage

The HTML files and audio MP3s need to go in blob storage, served via the existing CDN (`https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net`).

The student portal currently uses:
- Container `wwassets` (production/DevTest, from `WWAppStudent/appsettings.json`)
- Container `assets` (development, from `WWAppStudent/appsettings.Development.json`)

Suggested blob structure (Victor to decide container/path):
```
{container}/
  helpcontent/
    addition.html
    partitioning.html
    audio/
      help-addition-scenes/
        scene-0-intro.mp3
        scene-1-groups.mp3
        ...
      help-partitioning/
        scene-0-intro.mp3
        ...
```

The audio `src` paths in the HTML currently use relative paths (`../../audio/...`). These will need updating to absolute CDN URLs before upload:
```
https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/{container}/helpcontent/audio/...
```

### Step 2: Set Question.HelpURL

The `Question.HelpURL` field already exists (`nvarchar(1000)`) and flows through `GetNextQuestion` SP to `GetNextQuestionResult.HelpURL` on the client.

The SP already gates it by `IsHelpAllowed` on the session spec (line 238 of `GetNextQuestion.sql`):
```sql
RES.HelpURL = (SELECT CASE @isHelpAllowed WHEN 1 THEN Q.HelpURL ELSE NULL END)
```

So sessions need `QuizSessionSpec.IsHelpAllowed = 1` for the button to appear.

Set HelpURL to the CDN path with a `?scene=N` parameter:
```
https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/{container}/helpcontent/addition.html?scene=6
```

The scene number maps to the question sub-skill. Coverage map for Addition:

| Scene | Question types covered |
|-------|----------------------|
| 0 | (Intro) |
| 1 | Complete the sum / solve this addition |
| 2 | Which sum equals X? / What other sum equals? |
| 3 | Pairs that make 10 / select the pair |
| 4 | Doubles and near doubles |
| 5 | Word problems (altogether, in total, how many more) |
| 6 | Missing number / missing addend |
| 7 | Adding bigger numbers / adding tens |
| 8 | True or false addition statements |
| 9 | (Outro) |

**Bulk update:** QuestionStudio only allows setting HelpURL one question at a time. For hundreds of questions, a SQL UPDATE is needed:
```sql
-- Example: set all Addition questions under topic 'Addition' to scene 1 (basic sums)
UPDATE {schema}.Question
SET HelpURL = 'https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/{container}/helpcontent/addition.html?scene=1',
    LastModTime = GETDATE()
WHERE QuestionID IN (
    SELECT QC.QuestionID 
    FROM {schema}.QuestionClassification QC
    JOIN {schema}.Topic T ON T.TopicID = QC.TopicID
    WHERE T.TopicName = 'Addition'
)
```

We'd write a script to set the correct scene number per question based on the question text pattern.

### Step 3: Wire up the Get Help button

The button and event chain already exist but aren't connected:

**Current flow (verified):**
```
QuestionHeader.razor (button exists, NO @onclick)
  → InvokeHelpAsync() method exists (line 135) but button doesn't call it
    → OnGetHelp EventCallback → QuestionRenderer.HandleHelpRequestedAsync()
      → QuestionBody.RequestHelpAsync() → InteractionCoordinator
        → BaseQuestionTemplate.GetHelp() (line 847, only sets wasHelpUsed = true)
```

**3 changes needed:**

**1. `QuestionHeader.razor` (line ~28) — Add @onclick**

```html
<!-- Current -->
<button class="btn-help">
    <span>?</span> Help
</button>

<!-- Change to -->
<button class="btn-help" @onclick="InvokeHelpAsync">
    <span>?</span> Help
</button>
```

**2. `BaseQuestionTemplate.cs` (line ~847) — Open the help content**

Option A — new tab:
```csharp
protected async Task GetHelp()
{
    Logger?.LogInformation("Get help clicked for QuestionID {QuestionID}", QuestionData?.QuestionID);
    wasHelpUsed = true;
    
    if (!string.IsNullOrEmpty(QuestionData?.HelpURL))
    {
        await JS.InvokeVoidAsync("window.open", QuestionData.HelpURL, "_blank");
    }
}
```

Option B — modal with iframe:
```csharp
protected async Task GetHelp()
{
    Logger?.LogInformation("Get help clicked for QuestionID {QuestionID}", QuestionData?.QuestionID);
    wasHelpUsed = true;
    showHelpModal = true;
}
```

With modal markup added to the template:
```html
@if (showHelpModal && !string.IsNullOrEmpty(QuestionData?.HelpURL))
{
    <div class="help-modal-overlay" @onclick="() => showHelpModal = false">
        <div class="help-modal-content" @onclick:stopPropagation>
            <button class="help-modal-close" @onclick="() => showHelpModal = false">&times;</button>
            <iframe src="@QuestionData.HelpURL" style="width:100%;height:100%;border:none;"></iframe>
        </div>
    </div>
}
```

No CSP or iframe restrictions exist in the current codebase that would block this.

**3. `BaseQuestionTemplate.cs` (line ~108) — Update handler to await async GetHelp**

```csharp
// Current
InteractionCoordinator?.RegisterHelpHandler(async () =>
{
    GetHelp();
    await InvokeAsync(StateHasChanged);
});

// Change to
InteractionCoordinator?.RegisterHelpHandler(async () =>
{
    await GetHelp();
    await InvokeAsync(StateHasChanged);
});
```

### That's it

The `wasHelpUsed` flag already flows through to `SubmitAnswerRequest`, so analytics will track which students used help. No other backend changes needed.

## Existing Infrastructure Already Handled

| What | Status | Details |
|------|--------|---------|
| HelpURL field on Question | Exists | `nvarchar(1000)`, line 75 of Question.cs |
| HelpURL in GetNextQuestionResult | Exists | Flows to client via API |
| Session gating (IsHelpAllowed) | Exists | QuizSessionSpec.IsHelpAllowed, checked in SP |
| Help button UI | Exists | QuestionHeader.razor, just needs @onclick |
| Event chain to templates | Exists | Header → Renderer → Body → Coordinator → Template |
| wasHelpUsed tracking | Exists | Sent in SubmitAnswerRequest for analytics |
| QuestionStudio HelpURL field | Exists | Teachers can set it per question |
| CDN serving | Exists | Same Front Door serves images/audio already |

## Questions for Victor

1. **Modal or new tab?** — The HTML lessons work either way. No CSP restrictions detected.
2. **Which container/path?** — You mentioned `devtestblobs/helpcontent` previously. The student app uses `wwassets` in DevTest. Where should help content go?
3. **Audio file paths** — We'll update the HTML to use absolute CDN URLs before uploading. Just need to know the final container path.
