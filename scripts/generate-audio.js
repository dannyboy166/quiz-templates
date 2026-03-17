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
  { file: 'audio/word-match/question.mp3', text: 'Match the correct word to label the images. Look at each picture and drag the word that matches it.' },

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
  { file: 'audio/word-match/help.mp3', text: 'Look at each animated picture. Drag the right word to match. Check your answers when done!' },
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
  { file: 'audio/balloon-pop/question.mp3', text: 'Pop the balloon to complete the word! Look at the picture and choose the correct sound.' },

  // Hints for each word
  { file: 'audio/balloon-pop/hint-fish.mp3', text: 'This word ends with a quiet sound, like when you tell someone to be quiet: Shhh!' },
  { file: 'audio/balloon-pop/hint-chair.mp3', text: 'Think about the sound a train makes: Choo-choo!' },
  { file: 'audio/balloon-pop/hint-phone.mp3', text: 'These two letters together make an F sound!' },
  { file: 'audio/balloon-pop/hint-three.mp3', text: 'Put your tongue between your teeth and blow gently!' },
  { file: 'audio/balloon-pop/hint-ship.mp3', text: 'This sound is like telling someone to be quiet!' },
  { file: 'audio/balloon-pop/hint-cheese.mp3', text: 'What do you say when someone takes your picture? Say cheese!' },

  // Feedback
  { file: 'audio/balloon-pop/feedback-correct.mp3', text: 'Correct! Well done!' },
  { file: 'audio/balloon-pop/feedback-incorrect.mp3', text: 'Not quite. Let\'s try the next one!' },
  { file: 'audio/balloon-pop/feedback-complete.mp3', text: 'Quiz Complete! Great job popping those balloons!' },

  // Help
  { file: 'audio/balloon-pop/help.mp3', text: 'Look at the picture and the word with missing letters. Pop the balloon with the correct sound to complete the word!' },
];

// ==========================================
// CLOCK
// ==========================================
const clockAudio = [
  // Main question
  { file: 'audio/clock/question.mp3', text: 'Set each clock to show the time below it. Drag the hands to the correct positions!' },

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
  { file: 'audio/clock/help.mp3', text: 'The short hand shows the hour. The long hand shows the minutes. Drag them to match the time shown below each clock!' },
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
  { file: 'audio/dice-addition/feedback-complete.mp3', text: 'Time\'s up! Great job with those dice!' },

  // Start/Ready
  { file: 'audio/dice-addition/ready.mp3', text: 'Get ready! Add the dice as fast as you can!' },
];

// All templates
const allTemplates = {
  'word-match': wordMatchAudio,
  'base10-blocks': base10BlocksAudio,
  'balloon-pop': balloonPopAudio,
  'clock': clockAudio,
  'color-blocks': colorBlocksAudio,
  'dice-addition': diceAdditionAudio,
};

async function main() {
  // Get template from command line args
  const template = process.argv[2];

  let audioToGenerate;
  let templateName;

  if (template && allTemplates[template]) {
    audioToGenerate = allTemplates[template];
    templateName = template;
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
