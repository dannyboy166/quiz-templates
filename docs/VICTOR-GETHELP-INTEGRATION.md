# Get Help Integration Guide for Victor

## Demo Links

Two proof-of-concept help lessons are live:

- **Partitioning Numbers (9 scenes):** https://dannyboy166.github.io/quiz-templates/help/partitioning/
- **Addition (10 scenes):** https://dannyboy166.github.io/quiz-templates/help/addition/

Click the button, then play through the scenes. You can also deep-link to a specific scene:
- `?scene=3` — jumps straight to scene 3 (e.g., "Pairs of 10" in Addition)

## What Each Lesson Is

- **One self-contained HTML file** per topic (e.g., `addition.html`, `partitioning.html`)
- Each file has **multiple scenes/chapters** — one per question sub-skill
- Teacher voiceover (ElevenLabs) synced to animated HTML/CSS/JS visuals
- Scene navigation tabs, progress bar with seeking, replay, auto-advance
- **No external dependencies** — all inline CSS/JS, audio via `<audio>` tags
- **~28 files** for all Stage 1 Maths topics (not hundreds)

## How to Integrate

### Step 1: Upload files to blob storage

Upload the HTML files + audio MP3s to `devtestblobs/helpcontent/`:

```
devtestblobs/
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

The audio `src` paths in the HTML will need updating from relative (`../../audio/...`) to absolute CDN URLs:
```
https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/devtestblobs/helpcontent/audio/...
```

### Step 2: Set HelpURL on questions

Set `Question.HelpURL` to the CDN URL with a `?scene=N` parameter based on the question type:

```
https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/devtestblobs/helpcontent/addition.html?scene=6
```

The scene number maps to the question sub-skill. Each topic has a coverage map (documented in the HTML file). Example for Addition:

| Scene | Covers |
|-------|--------|
| 0 | Intro |
| 1 | Basic sums / complete the sum |
| 2 | Which sum equals X? |
| 3 | Pairs that make 10 |
| 4 | Doubles and near doubles |
| 5 | Word problems |
| 6 | Missing number / missing addend |
| 7 | Adding bigger numbers / adding tens |
| 8 | True or false addition statements |
| 9 | Outro |

### Step 3: Wire up the button (3 changes)

The Get Help button and event chain are already built but not connected. Here are the changes:

**1. `QuestionHeader.razor` — Add onclick to the button**

Current (line ~28):
```html
<button class="btn-help">
    <span>?</span> Help
</button>
```

Change to:
```html
<button class="btn-help" @onclick="InvokeHelpAsync">
    <span>?</span> Help
</button>
```

**2. `BaseQuestionTemplate.cs` — Open the help URL**

Current `GetHelp()` method (line ~847):
```csharp
protected void GetHelp()
{
    Logger?.LogInformation("Get help clicked for QuestionID {QuestionID}", QuestionData?.QuestionID);
    wasHelpUsed = true;
}
```

Change to (Option A — open in new tab):
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

Or (Option B — open in modal/iframe within the portal):
```csharp
protected async Task GetHelp()
{
    Logger?.LogInformation("Get help clicked for QuestionID {QuestionID}", QuestionData?.QuestionID);
    wasHelpUsed = true;
    showHelpModal = true;  // Toggle a modal that contains an iframe
}
```

If using the modal approach, add to the template markup:
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

**3. Update the InteractionCoordinator registration** in `BaseQuestionTemplate.cs` (line ~108):

Current:
```csharp
InteractionCoordinator?.RegisterHelpHandler(async () =>
{
    GetHelp();
    await InvokeAsync(StateHasChanged);
});
```

Change to (if GetHelp is now async):
```csharp
InteractionCoordinator?.RegisterHelpHandler(async () =>
{
    await GetHelp();
    await InvokeAsync(StateHasChanged);
});
```

### That's it!

The `wasHelpUsed` tracking already flows through to `SubmitAnswerRequest`, so analytics will show which students used help. No other backend changes needed.

## Architecture Summary

```
Student clicks "Get Help"
    ↓
QuestionHeader (@onclick="InvokeHelpAsync")
    ↓
QuestionRenderer (HandleHelpRequestedAsync)
    ↓
QuestionBody → InteractionCoordinator
    ↓
BaseQuestionTemplate.GetHelp()
    ↓
Opens HelpURL (CDN → helpcontent/addition.html?scene=6)
    ↓
Self-contained HTML lesson plays in browser
```

## Questions for Victor

1. **Modal or new tab?** — Do you want the help lesson to open as a modal overlay within the portal, or in a new browser tab? Both work.
2. **Audio paths** — Should the audio MP3s sit alongside the HTML in `helpcontent/`, or in a separate `helpcontent/audio/` subfolder?
3. **Teacher video** — The lessons include the teacher character (`teacher-transparent.webm`). Should this also go in blob storage, or skip it for now?
