/**
 * Audio Generation Script for Quiz Templates
 * Uses ElevenLabs API to generate professional voice audio
 *
 * Usage: node scripts/generate-audio.js
 */

require('dotenv').config();
const fs = require('fs');
const path = require('path');

const API_KEY = process.env.ELEVENLABS_API_KEY;
const VOICE_ID = process.env.ELEVENLABS_VOICE_ID;

if (!API_KEY || !VOICE_ID) {
  console.error('Missing ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID in .env file');
  process.exit(1);
}

// ==========================================
// WORD MATCH
// ==========================================
const wordMatchAudio = [
  // Main question
  { file: 'audio/word-match/question.mp3', text: 'Match each word with the correct picture.' },

  // Page 1 hints - Common animals
  { file: 'audio/word-match/hint-dog.mp3', text: 'This animal barks and is man\'s best friend!' },
  { file: 'audio/word-match/hint-cat.mp3', text: 'This animal meows and loves to sleep!' },
  { file: 'audio/word-match/hint-fish.mp3', text: 'This animal swims in water!' },
  { file: 'audio/word-match/hint-frog.mp3', text: 'This animal says ribbit and jumps!' },
  { file: 'audio/word-match/hint-bee.mp3', text: 'This insect makes honey!' },
  { file: 'audio/word-match/hint-ant.mp3', text: 'This tiny insect is very strong!' },

  // Page 2 hints - Safari animals
  { file: 'audio/word-match/hint-elephant.mp3', text: 'This big animal has a long trunk!' },
  { file: 'audio/word-match/hint-giraffe.mp3', text: 'This animal has a very long neck!' },
  { file: 'audio/word-match/hint-zebra.mp3', text: 'This animal has black and white stripes!' },
  { file: 'audio/word-match/hint-horse.mp3', text: 'People ride on this animal!' },
  { file: 'audio/word-match/hint-sheep.mp3', text: 'This fluffy animal says baa!' },
  { file: 'audio/word-match/hint-goat.mp3', text: 'This animal has horns and a beard!' },

  // Page 3 hints - More animals
  { file: 'audio/word-match/hint-rabbit.mp3', text: 'This animal has long ears and hops!' },
  { file: 'audio/word-match/hint-chicken.mp3', text: 'This bird lays eggs!' },
  { file: 'audio/word-match/hint-snake.mp3', text: 'This animal slithers on the ground!' },
  { file: 'audio/word-match/hint-dolphin.mp3', text: 'This smart animal lives in the ocean!' },
  { file: 'audio/word-match/hint-whale.mp3', text: 'This is the biggest animal in the sea!' },
  { file: 'audio/word-match/hint-bat.mp3', text: 'This animal flies at night!' },

  // Page 4 hints - Mixed
  { file: 'audio/word-match/hint-mouse.mp3', text: 'This tiny animal loves cheese!' },
  { file: 'audio/word-match/hint-deer.mp3', text: 'This animal has antlers!' },
  { file: 'audio/word-match/hint-snail.mp3', text: 'This slow animal carries its house!' },
  { file: 'audio/word-match/hint-dinosaur.mp3', text: 'This animal lived millions of years ago!' },
  { file: 'audio/word-match/hint-crocodile.mp3', text: 'This reptile has big teeth!' },
  { file: 'audio/word-match/hint-car.mp3', text: 'You drive this on the road!' },

  // Feedback
  { file: 'audio/word-match/feedback-perfect.mp3', text: 'Perfect! All words matched correctly!' },
  { file: 'audio/word-match/feedback-keep-trying.mp3', text: 'Keep trying! You can do it!' },
  { file: 'audio/word-match/feedback-complete.mp3', text: 'Quiz Complete! You matched all 24 words correctly!' },

  // Help
  { file: 'audio/word-match/help.mp3', text: 'Say the name of the animal. What sound do you hear at the beginning of the word? Drag the correct word to the matching picture. Remember to check your answers. Match all 6 words to a picture. Let\'s go!' },
];

// ==========================================
// BASE 10 BLOCKS
// ==========================================
const base10BlocksAudio = [
  // Main question
  { file: 'audio/base10-blocks/question.mp3', text: 'How many blocks are there? Count the blue flats for hundreds, red rods for tens, and orange cubes for ones.' },

  // Hints for each place value
  { file: 'audio/base10-blocks/hint-hundreds.mp3', text: 'Count the big blue flats. Each one is worth one hundred!' },
  { file: 'audio/base10-blocks/hint-tens.mp3', text: 'Count the red rods. Each one is worth ten!' },
  { file: 'audio/base10-blocks/hint-ones.mp3', text: 'Count the small orange cubes. Each one is worth one!' },

  // Feedback
  { file: 'audio/base10-blocks/feedback-correct.mp3', text: 'Awesome! That\'s right!' },
  { file: 'audio/base10-blocks/feedback-incorrect.mp3', text: 'Not quite. Give it another go!' },
  { file: 'audio/base10-blocks/feedback-complete.mp3', text: 'Quiz Complete! Great job counting those blocks!' },

  // Help
  { file: 'audio/base10-blocks/help.mp3', text: 'Count the blocks to find the total. Blue flats are hundreds, red rods are tens, and orange cubes are ones. Add them all together!' },
];

async function generateAudio(text, outputPath) {
  console.log(`Generating: ${outputPath}`);

  try {
    const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}`, {
      method: 'POST',
      headers: {
        'xi-api-key': API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: text,
        model_id: 'eleven_multilingual_v2',
        output_format: 'mp3_44100_128'
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    const buffer = await response.arrayBuffer();

    // Ensure directory exists
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    fs.writeFileSync(outputPath, Buffer.from(buffer));
    console.log(`  ✓ Saved: ${outputPath}`);

    // Small delay to avoid rate limiting
    await new Promise(r => setTimeout(r, 500));

  } catch (error) {
    console.error(`  ✗ Failed: ${outputPath} - ${error.message}`);
  }
}

// ==========================================
// BALLOON POP
// ==========================================
const balloonPopAudio = [
  // Main question
  { file: 'audio/balloon-pop/question.mp3', text: 'Pop the balloon with the digraph that completes this word.' },

  // Hints for each word
  { file: 'audio/balloon-pop/hint-fish.mp3', text: 'This word ends with a quiet sound, like when you tell someone to be quiet: Shhh!' },
  { file: 'audio/balloon-pop/hint-sheep.mp3', text: 'This word starts with a quiet sound, like when you tell someone to be quiet: Shhh!' },
  { file: 'audio/balloon-pop/hint-chicken.mp3', text: 'Think about the sound a train makes: Choo-choo! This word starts with that sound.' },
  { file: 'audio/balloon-pop/hint-whale.mp3', text: 'This sound is at the start of question words like what and where!' },
  { file: 'audio/balloon-pop/hint-dolphin.mp3', text: 'These two letters together make an F sound!' },
  { file: 'audio/balloon-pop/hint-elephant.mp3', text: 'These two letters make the same sound as the letter F!' },

  // Feedback
  { file: 'audio/balloon-pop/feedback-correct.mp3', text: 'Correct! Well done!' },
  { file: 'audio/balloon-pop/feedback-incorrect.mp3', text: 'Not quite. Let\'s try the next one!' },
  { file: 'audio/balloon-pop/feedback-complete.mp3', text: 'Quiz Complete! Great job popping those balloons!' },

  // Help
  { file: 'audio/balloon-pop/help.mp3', text: 'Look at the picture and the word with missing letters. Pop the balloon with the digraph that completes this word. Each balloon has a different digraph. A digraph is 2 letters that make one sound. Like ch in chop, sh in ship, th in think, and ph in phone.' },
];

// ==========================================
// CLOCK
// ==========================================
const clockAudio = [
  // Main question
  { file: 'audio/clock/question.mp3', text: 'Set each clock to show the correct time.' },

  // Difficulty intros
  { file: 'audio/clock/difficulty-hours.mp3', text: 'Hours only mode! Set the clocks to show times like 3 o\'clock.' },
  { file: 'audio/clock/difficulty-half.mp3', text: 'Half hours mode! Set the clocks to show times like half past 3.' },
  { file: 'audio/clock/difficulty-quarters.mp3', text: 'Quarter hours mode! Set the clocks to quarter past and quarter to times.' },
  { file: 'audio/clock/difficulty-five.mp3', text: 'Five minute intervals! Set the clocks to any five-minute time.' },

  // Hints
  { file: 'audio/clock/hint-hour.mp3', text: 'The short hand points to the hour. Look at the number below the clock!' },
  { file: 'audio/clock/hint-minute.mp3', text: 'The long hand points to the minutes. Remember, each number is 5 minutes!' },
  { file: 'audio/clock/hint-all-correct.mp3', text: 'All your clocks look right! Click Check All Answers to confirm!' },

  // Feedback
  { file: 'audio/clock/feedback-correct.mp3', text: 'Well done! All clocks are set correctly!' },
  { file: 'audio/clock/feedback-incorrect.mp3', text: 'Not quite right. Check the clocks highlighted in red.' },
  { file: 'audio/clock/feedback-complete.mp3', text: 'Quiz Complete! You\'re a clock reading champion!' },

  // Help
  { file: 'audio/clock/help.mp3', text: 'Short hand tells us what hour it is. Long hand tells us the minutes. For times like 3 o\'clock, the long hand always points to 12. Drag the short hand to change the hour. Drag the long hand to change the minutes.' },
];

// ==========================================
// COLOR BLOCKS
// ==========================================
const colorBlocksAudio = [
  // Main question
  { file: 'audio/color-blocks/question.mp3', text: 'Click the blocks to colour them and make the target number!' },

  // Hints
  { file: 'audio/color-blocks/hint-hundreds.mp3', text: 'Each big flat represents 100. Count how many hundreds you need!' },
  { file: 'audio/color-blocks/hint-tens.mp3', text: 'Each tall column has 10 blocks. Count how many tens you need!' },
  { file: 'audio/color-blocks/hint-ones.mp3', text: 'Each small cube is worth 1. Count how many ones you need!' },

  // Feedback
  { file: 'audio/color-blocks/feedback-correct.mp3', text: 'Perfect! You coloured the right number of blocks!' },
  { file: 'audio/color-blocks/feedback-incorrect.mp3', text: 'Not quite. Try counting the blocks again!' },
  { file: 'audio/color-blocks/feedback-complete.mp3', text: 'Quiz Complete! Great job colouring those blocks!' },

  // Help
  { file: 'audio/color-blocks/help.mp3', text: 'Click blocks to colour them. Big flats are 100, tall columns are 10, and small cubes are 1. Colour enough to match the target number!' },
];

// ==========================================
// DICE ADDITION
// ==========================================
const diceAdditionAudio = [
  // Main question
  { file: 'audio/dice-addition/question.mp3', text: 'Add up the dice as fast as you can! Type your answer and press enter.' },

  // Feedback
  { file: 'audio/dice-addition/feedback-correct.mp3', text: 'Correct!' },
  { file: 'audio/dice-addition/feedback-incorrect.mp3', text: 'Oops! Plus 5 seconds!' },
  { file: 'audio/dice-addition/feedback-complete.mp3', text: 'All done! Great job with those dice!' },

  // Start/Ready
  { file: 'audio/dice-addition/ready.mp3', text: 'Get ready! Add the dice as fast as you can!' },

  // Help
  { file: 'audio/dice-addition/help.mp3', text: 'Tap the table to roll the dice. Count the dots on the top face of each dice and add them up. Click the correct answer. Wrong answers add 5 seconds. Complete 10 rounds as fast as you can!' },
];

// ==========================================
// FRACTIONS
// ==========================================
const fractionsAudio = [
  // Main question
  { file: 'audio/fractions/question.mp3', text: 'Colour parts of the shape to match the fraction.' },

  // Hints
  { file: 'audio/fractions/hint.mp3', text: 'The top number tells you how many parts to colour. The bottom number tells you how many parts there are in total!' },

  // Feedback
  { file: 'audio/fractions/feedback-correct.mp3', text: 'Excellent! You coloured the correct fraction!' },
  { file: 'audio/fractions/feedback-incorrect.mp3', text: 'Not quite. Try counting the parts again!' },
  { file: 'audio/fractions/feedback-complete.mp3', text: 'Quiz Complete! You\'re a fractions superstar!' },

  // Help
  { file: 'audio/fractions/help.mp3', text: 'The bottom number tells us the whole is cut into equal parts. The top number tells us how many of those parts we have. These parts are smaller pieces of one whole.' },
];

// ==========================================
// SKIP COUNTING
// ==========================================
const skipCountingAudio = [
  // Main question
  { file: 'audio/skip-counting/question.mp3', text: 'Fill in the missing numbers! Count by the skip number to complete the pattern.' },

  // Hints
  { file: 'audio/skip-counting/hint.mp3', text: 'Add the skip number to the previous number to find the next one!' },

  // Feedback
  { file: 'audio/skip-counting/feedback-correct.mp3', text: 'Perfect! You completed the pattern!' },
  { file: 'audio/skip-counting/feedback-incorrect.mp3', text: 'Some numbers are wrong. Check your counting!' },
  { file: 'audio/skip-counting/feedback-complete.mp3', text: 'Quiz Complete! Great job skip counting!' },

  // Help
  { file: 'audio/skip-counting/help.mp3', text: 'Look at the numbers. Can you see a pattern? What are you counting by? Type the missing numbers in the yellow boxes.' },
];

// ==========================================
// DRAG DROP
// ==========================================
const dragDropAudio = [
  // Main question
  { file: 'audio/drag-drop/question.mp3', text: 'Sort the shapes into the correct jars! Drag each shape to where it belongs.' },

  // Feedback
  { file: 'audio/drag-drop/feedback-correct.mp3', text: 'Well done! All shapes sorted correctly!' },
  { file: 'audio/drag-drop/feedback-incorrect.mp3', text: 'Some shapes are in the wrong jar. Try again!' },
  { file: 'audio/drag-drop/feedback-complete.mp3', text: 'Quiz Complete! You sorted all the shapes!' },

  // Help
  { file: 'audio/drag-drop/help.mp3', text: 'Look at each shape and count its sides. Then drag it to the jar with that number!' },
];

// ==========================================
// LINE MATCH
// ==========================================
const lineMatchAudio = [
  // Main question
  { file: 'audio/line-match/question.mp3', text: 'Draw lines to match the items on the left with their matches on the right!' },

  // Hints
  { file: 'audio/line-match/hint.mp3', text: 'Look carefully at each item and think about what it matches with!' },

  // Feedback
  { file: 'audio/line-match/feedback-correct.mp3', text: 'Perfect! All matches are correct!' },
  { file: 'audio/line-match/feedback-incorrect.mp3', text: 'Not quite right. Try again!' },
  { file: 'audio/line-match/feedback-complete.mp3', text: 'Quiz Complete! Great job matching!' },

  // Help
  { file: 'audio/line-match/help.mp3', text: 'Pick a colour, tap an item on the left, then tap its match on the right. A line will connect them!' },
];

// ==========================================
// MISSING LETTERS
// ==========================================
const missingLettersAudio = [
  // Main question
  { file: 'audio/missing-letters/question.mp3', text: 'Choose the missing letters to complete the word!' },

  // Hints
  { file: 'audio/missing-letters/hint.mp3', text: 'Remember: i before e, except after c! Look at the letter before the blank.' },

  // Feedback
  { file: 'audio/missing-letters/feedback-correct.mp3', text: 'Correct! Well done!' },
  { file: 'audio/missing-letters/feedback-incorrect.mp3', text: 'Not quite. Let me show you the right answer!' },
  { file: 'audio/missing-letters/feedback-complete.mp3', text: 'Quiz Complete! Great spelling practice!' },

  // Help
  { file: 'audio/missing-letters/help.mp3', text: 'Look at the word with missing letters. Choose which letters complete the word correctly. Remember: i before e, except after c!' },
];

// ==========================================
// NUMBER ORDER
// ==========================================
const numberOrderAudio = [
  // Main question
  { file: 'audio/number-order/question.mp3', text: 'Put the numbers in order from smallest to biggest! Drag them into the circles.' },

  // Hints
  { file: 'audio/number-order/hint.mp3', text: 'Start with the smallest number. Which number is the smallest?' },

  // Feedback
  { file: 'audio/number-order/feedback-correct.mp3', text: 'Perfect! The numbers are in the right order!' },
  { file: 'audio/number-order/feedback-incorrect.mp3', text: 'Not quite right. Keep trying!' },
  { file: 'audio/number-order/feedback-complete.mp3', text: 'Quiz Complete! Great job ordering those numbers!' },

  // Help
  { file: 'audio/number-order/help.mp3', text: 'Drag the number bubbles into the circles. Put them in order from smallest to biggest. The smallest number goes first!' },
];

// ==========================================
// PICTURE EQUATIONS
// ==========================================
const pictureEquationsAudio = [
  // Main question
  { file: 'audio/picture-equations/question.mp3', text: 'Complete the number sentence.' },

  // Hints
  { file: 'audio/picture-equations/hint.mp3', text: 'Count the pictures carefully. The crossed-out ones are being taken away!' },

  // Feedback
  { file: 'audio/picture-equations/feedback-correct.mp3', text: 'Correct! Great counting!' },
  { file: 'audio/picture-equations/feedback-incorrect.mp3', text: 'Not quite right. Try counting again!' },
  { file: 'audio/picture-equations/feedback-complete.mp3', text: 'Quiz Complete! Great job with those equations!' },

  // Help
  { file: 'audio/picture-equations/help.mp3', text: 'Fill in the missing number to complete this number sentence. Look at the pictures. Some have a red line through them, meaning they have been taken away. Subtraction means to start with a number and take some away to see what is left. Addition means adding more, putting groups together to find the total. Type a number in the empty box to make this number sentence correct.' },
];

// ==========================================
// SOUND SELECT
// ==========================================
const soundSelectAudio = [
  // Main question
  { file: 'audio/sound-select/question.mp3', text: 'Select the words that begin with the target letter!' },

  // Hints for each sound
  { file: 'audio/sound-select/hint-c.mp3', text: 'Say each picture\'s name out loud. Does it start with c, like cat or car?' },
  { file: 'audio/sound-select/hint-s.mp3', text: 'Say each picture\'s name out loud. Does it start with s, like sun or snake?' },
  { file: 'audio/sound-select/hint-d.mp3', text: 'Say each picture\'s name out loud. Does it start with d, like dog or dinosaur?' },

  // Feedback
  { file: 'audio/sound-select/feedback-correct.mp3', text: 'Perfect! You found all the matches!' },
  { file: 'audio/sound-select/feedback-incorrect.mp3', text: 'Not quite right. Try again!' },
  { file: 'audio/sound-select/feedback-complete.mp3', text: 'Quiz Complete! Great job with those sounds!' },

  // Help
  { file: 'audio/sound-select/help.mp3', text: 'Look at the letter. What sound does it make? Find pictures that begin with that sound. Tap the pictures that start with that sound.' },
];

// ==========================================
// SPELLING (Phonics)
// ==========================================
const spellingAudio = [
  // Main question
  { file: 'audio/spelling/question.mp3', text: 'Blend the sounds together to make a word. Look at each picture and drag the sounds to make the word.' },

  // Hints
  { file: 'audio/spelling/hint.mp3', text: 'Find the first sound of the word. What sound does the picture start with?' },

  // Feedback
  { file: 'audio/spelling/feedback-correct.mp3', text: 'Page complete! Well done!' },
  { file: 'audio/spelling/feedback-incorrect.mp3', text: 'Keep going! You can do it!' },
  { file: 'audio/spelling/feedback-complete.mp3', text: 'Amazing! You made all the words!' },

  // Help
  { file: 'audio/spelling/help.mp3', text: 'Look at the picture. Drag each sound into the boxes to make the word. Blend the sounds together to check your answers. See if you can make all the words using your phonics knowledge!' },
];

// ==========================================
// SPELLING RULES
// ==========================================
const spellingRulesAudio = [
  // Main question
  { file: 'audio/spelling-rules/question.mp3', text: 'Apply the spelling rule! Choose the correct ending for each word.' },

  // Hints
  { file: 'audio/spelling-rules/hint.mp3', text: 'Think about the spelling rule. Look at the base word and apply the pattern!' },

  // Feedback
  { file: 'audio/spelling-rules/feedback-correct.mp3', text: 'Correct! You applied the rule perfectly!' },
  { file: 'audio/spelling-rules/feedback-incorrect.mp3', text: 'Not quite. Check the spelling rule and try again!' },
  { file: 'audio/spelling-rules/feedback-complete.mp3', text: 'Quiz Complete! Great spelling work!' },

  // Help
  { file: 'audio/spelling-rules/help.mp3', text: 'Read the spelling rule carefully. Look at each word and choose the option that follows the rule!' },
];

// ==========================================
// WORD SORT
// ==========================================
const wordSortAudio = [
  // Main question
  { file: 'audio/word-sort/question.mp3', text: 'Sort the words into the correct lists! Drag each word to where it belongs.' },

  // Hints
  { file: 'audio/word-sort/hint.mp3', text: 'Read each word carefully. Think about which category it fits into!' },

  // Feedback
  { file: 'audio/word-sort/feedback-correct.mp3', text: 'Perfect! All words sorted correctly!' },
  { file: 'audio/word-sort/feedback-incorrect.mp3', text: 'Some words are in the wrong list. Try again!' },
  { file: 'audio/word-sort/feedback-complete.mp3', text: 'Quiz Complete! Great job sorting those words!' },

  // Help
  { file: 'audio/word-sort/help.mp3', text: 'Read each word from the list. Drag it to the correct category. Look at the spelling pattern to help you decide!' },
];

// All templates
const allTemplates = {
  'word-match': wordMatchAudio,
  'base10-blocks': base10BlocksAudio,
  'balloon-pop': balloonPopAudio,
  'clock': clockAudio,
  'color-blocks': colorBlocksAudio,
  'dice-addition': diceAdditionAudio,
  'fractions': fractionsAudio,
  'skip-counting': skipCountingAudio,
  'drag-drop': dragDropAudio,
  'line-match': lineMatchAudio,
  'missing-letters': missingLettersAudio,
  'number-order': numberOrderAudio,
  'picture-equations': pictureEquationsAudio,
  'sound-select': soundSelectAudio,
  'spelling': spellingAudio,
  'spelling-rules': spellingRulesAudio,
  'word-sort': wordSortAudio,
};

async function main() {
  // Get template and optional filter from command line args
  const template = process.argv[2];
  const filter = process.argv[3]; // Optional: filter to specific files (e.g., "question", "help")

  let audioToGenerate;
  let templateName;

  if (template && allTemplates[template]) {
    audioToGenerate = allTemplates[template];
    templateName = template;

    // If filter provided, only generate matching files
    if (filter) {
      audioToGenerate = audioToGenerate.filter(item =>
        item.file.toLowerCase().includes(filter.toLowerCase())
      );
      templateName = `${template} (filter: ${filter})`;

      if (audioToGenerate.length === 0) {
        console.error(`No files matching "${filter}" in template "${template}"`);
        console.log('Available files:');
        allTemplates[template].forEach(item => console.log(`  - ${item.file}`));
        process.exit(1);
      }
    }
  } else if (template) {
    console.error(`Unknown template: ${template}`);
    console.log('Available templates:', Object.keys(allTemplates).join(', '));
    process.exit(1);
  } else {
    // Generate all if no template specified
    audioToGenerate = Object.values(allTemplates).flat();
    templateName = 'ALL';
  }

  console.log('='.repeat(50));
  console.log('ElevenLabs Audio Generation Script');
  console.log('='.repeat(50));
  console.log(`Voice ID: ${VOICE_ID}`);
  console.log(`Template: ${templateName}`);
  console.log(`Files to generate: ${audioToGenerate.length}`);
  console.log('');
  console.log('Usage: node scripts/generate-audio.js [template] [filter]');
  console.log('  e.g. node scripts/generate-audio.js word-match');
  console.log('  e.g. node scripts/generate-audio.js word-match question');
  console.log('  e.g. node scripts/generate-audio.js word-match help');
  console.log('='.repeat(50));
  console.log('');

  for (const item of audioToGenerate) {
    await generateAudio(item.text, item.file);
  }

  console.log('');
  console.log('='.repeat(50));
  console.log('Done!');
  console.log('='.repeat(50));
}

main();
