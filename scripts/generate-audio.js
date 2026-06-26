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

async function generateAudio(text, outputPath, speed = 0.9) {
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
        output_format: 'mp3_44100_128',
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
          speed: speed
        }
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

// ==========================================
// HELP - PARTITIONING NUMBERS
// ==========================================
const helpPartitioningAudio = [
  { file: 'audio/help-partitioning/scene-0-intro.mp3',
    text: "Hello! Today we're going to partition numbers. To partition means to break a number into smaller parts — And one useful way is to break the number into tens and ones. Once you can do that, you can answer lots of different questions, so let's work through them together." },
  { file: 'audio/help-partitioning/scene-1-tens-and-ones.mp3',
    text: "Let's start with the number 34. The three is in the tens place, so it tells us there are 3 tens. The four is in the ones place, so it tells us there are 4 ones. We can build 34 by filling three ten-frames to make three tens, then adding four single counters for the ones. So 34 is 3 tens and 4 ones." },
  { file: 'audio/help-partitioning/scene-2-how-many.mp3',
    text: "Sometimes a question just asks how many tens, or how many ones, are in a number. Look at 34 again. The tens digit is 3, so there are 3 tens — and 3 tens is the same as 30. The ones digit is 4, so there are 4 ones. So in 34 there are 3 tens and 4 ones." },
  { file: 'audio/help-partitioning/scene-3-true-or-false.mp3',
    text: "Some questions give you a statement and ask if it's true or false. For example: 34 is the same as 3 tens and 4 ones. To check, we count the tens — yes, 3 tens — and the ones — yes, 4 ones. Everything matches, so the answer is true. If either the tens or the ones didn't match, it would be false." },
  { file: 'audio/help-partitioning/scene-4-another-way.mp3',
    text: "Here's something clever. A number can be partitioned in more than one way. We know 34 is 3 tens and 4 ones. But watch — we can break up one ten and turn it into ten ones. Now we have 2 tens and 14 ones. It looks different, but it's still 34. We could even break apart all the tens to make 34 ones. So when a question asks for another way to show a number, remember that one ten is the same as ten ones, you can trade them and the number stays the same." },
  { file: 'audio/help-partitioning/scene-5-picture.mp3',
    text: "Often you'll see a picture made of blocks. The long blocks are tens and the small blocks are ones. To name the number, count the tens first, then the ones. Here we have 3 tens and 4 ones, so the picture shows 34. And if you ever spot a large flat block, that's one hundred — count those first, then the tens, then the ones." },
  { file: 'audio/help-partitioning/scene-6-tally.mp3',
    text: "A tally is a quick way to keep count. The marks are grouped into bundles of five — four straight lines with one line crossed through them. To read a tally, count the bundles by fives first, then count on the extra marks. Here we have two bundles — that's ten — and two extra marks, so the tally shows 12." },
  { file: 'audio/help-partitioning/scene-7-biggest-smallest.mp3',
    text: "Last one. Sometimes you're given some digits and asked to make the biggest or the smallest number. The important thing to remember is place value. To make the biggest number, put the biggest digit first. To make the smallest, put the smallest digit first. With the digits 4, 1 and 6, the biggest number is six hundred and forty-one, and the smallest is one hundred and forty-six." },
  { file: 'audio/help-partitioning/scene-8-outro.mp3',
    text: "Now it's your turn! Now try partitioning some numbers yourself." },
];

// ==========================================
// HELP - ADDITION
// ==========================================
const helpAdditionScenesAudio = [
  { file: 'audio/help-addition-scenes/scene-0-intro.mp3',
    text: "Hello! Today we're going to learn about addition. Adding means putting things together to find how many altogether. Let's look at some different ways addition questions might be asked." },
  { file: 'audio/help-addition-scenes/scene-1-groups.mp3',
    text: "Let's start with the simplest kind. I have 3 apples here, and 2 apples here. When I push them together, I get 5 altogether. We write that as 3 plus 2 equals 5. So when a question says complete the sum or solve this addition problem, just put the groups together and count how many altogether." },
  { file: 'audio/help-addition-scenes/scene-2-which-sum.mp3',
    text: "Sometimes you're given a target number and asked which sum makes it. For example: which sum equals 7? Is it 3 plus 4, or 2 plus 6? Let's check. 3 plus 4 is 7 — yes, that's the one! And 2 plus 6 is 8 — that's not 7, so it's not the right answer. So 3 plus 4 is the answer. Here's something interesting: you can swap the numbers around and the answer stays the same. 3 plus 4 equals 4 plus 3. Both make 7." },
  { file: 'audio/help-addition-scenes/scene-3-pairs-ten.mp3',
    text: "Pairs that make 10 are really important because they help us solve bigger addition questions. Here are the pairs: 0 and 10, 1 and 9, 2 and 8, 3 and 7, 4 and 6, 5 and 5. Each pair adds to 10. So if a question asks you to select the pair that adds to 10 and you see 3 and 7, you know that's a match." },
  { file: 'audio/help-addition-scenes/scene-4-doubles.mp3',
    text: "Doubles are easy to spot — both numbers are the same! Double 6 means 6 plus 6, which is 12. Double 8 is 8 plus 8, which is 16. And here's a useful strategy - near doubles. If you know double 6 is 12, then 6 plus 7 is just one more — 13!" },
  { file: 'audio/help-addition-scenes/scene-5-word-problems.mp3',
    text: "Word problems tell a little story. The trick is finding the numbers and the word that tells you to add. Listen for words like altogether, in total, add, joins, or gets more. Here's one: Ben has 7 toy cars. He gets 5 more. How many altogether? Find the numbers — 7 and 5. The word altogether tells us to add. 7 plus 5 equals 12." },
  { file: 'audio/help-addition-scenes/scene-6-missing-number.mp3',
    text: "Missing number questions have a gap you need to fill. Something like: 8 plus what equals 13? Think of it as: what do I need to add to 8 to get to 13? You can count on from 8 — nine, ten, eleven, twelve, thirteen — that's 5 jumps or we might also say 5 counts. So the missing number is 5. You can also think backwards: 13 take away 8 is 5." },
  { file: 'audio/help-addition-scenes/scene-7-bigger-numbers.mp3', speed: 0.8,
    text: "When the numbers get bigger, use what you know about tens and ones. Let's try 29 plus 10. We're just adding one ten, so the tens digit goes up by one — 29 becomes 39. Easy! What about 28 plus 30? That's adding 3 tens. The tens digit goes from 2 to 5 — 28 becomes 58. For trickier ones like 36 plus 25 we can break up the numbers to make it easier to solve, add the tens first: 30 plus 20 is 50. Then add the ones: 6 plus 5 is 11. 50 plus 11 is 61 because 50 and 10 make 60, then one more makes 61." },
  { file: 'audio/help-addition-scenes/scene-8-true-false.mp3', speed: 0.8,
    text: "True or false questions give you a finished sum and ask if it's right. For example: 46 plus 31 equals 78. Is that true or false? Let's check. Add the tens: 40 plus 30 is 70. Add the ones: 6 plus 1 is 7. 70 plus 7 is 77, not 78. So the answer is false! Always work it out yourself to check." },
  { file: 'audio/help-addition-scenes/scene-9-outro.mp3',
    text: "Now it's your turn! Try solving some addition questions yourself." },
];

// ==========================================
// HELP - HOMOPHONES
// ==========================================
const helpHomophonesAudio = [
  { file: 'audio/help-homophones/scene-0-intro.mp3',
    text: "Hello! Today we're learning about homophones. Homophones are words that sound the same but have different spellings and different meanings. Like blue and blew — they sound the same, but one is a colour and the other means the wind blew. Let's learn how to pick the right one." },
  { file: 'audio/help-homophones/scene-1-to-too-two.mp3',
    text: "These three words all sound the same but mean different things. Two is the number 2. I have two cats. Too means also, or too much. I want to come too! It's too hot! To is used for everything else — going to the shops, to run, to play. If you're talking about the number, use two. If you mean also or too much, use too. For everything else, use to." },
  { file: 'audio/help-homophones/scene-2-there-their-theyre.mp3',
    text: "These three sound the same too. There is a place. The ball is over there. Their means belonging to them. That is their house. They're is short for they are. They're playing outside. A good trick: if you can replace the word with they are and it still makes sense, use they're. If it's about a place, use there. If it belongs to someone, use their." },
  { file: 'audio/help-homophones/scene-3-common-pairs.mp3',
    text: "Let's look at some common pairs you'll see in questions. Buy means to purchase something. Bye means goodbye. We are going to buy shoes — that's buy with a u-y. Sun is the star in the sky. Son is a male child. Mark has a son — that's son with an o. Sea is the ocean. See is what your eyes do. Hair is on your head. Hare is a type of rabbit. No is the opposite of yes. Know means to understand something." },
  { file: 'audio/help-homophones/scene-4-fill-blank.mp3',
    text: "Most homophone questions give you a sentence with a blank. Her dress is blank. Is it blew or blue? Think about the meaning. The dress is a colour — blue! Blew means the wind blew — that doesn't make sense for a dress. The blank ran very fast. Is it hair or hare? A hare is a fast animal. Hair doesn't run. So the answer is hare. Always read the sentence and think about what the word means — not just how it sounds." },
  { file: 'audio/help-homophones/scene-5-correct-sentence.mp3',
    text: "Some questions show you sentences and ask which one uses the homophone correctly. Which sentence uses two correctly? I have two cats. That's right — two means the number! I like going two the shops. That's wrong — it should be to, not two. Which sentence uses the correct homophone? I no how to spell, or I know how to spell? I know how to spell — know means to understand. No is the opposite of yes. Read each sentence carefully and check if the meaning matches the spelling." },
  { file: 'audio/help-homophones/scene-6-outro.mp3',
    text: "Now it's your turn! Try picking the right homophones yourself." },
];

// ==========================================
// HELP - SUBTRACTION
// ==========================================
const helpSubtractionAudio = [
  { file: 'audio/help-subtraction/scene-0-intro.mp3',
    text: "Hello! Today we're learning about subtraction. Subtracting means taking away — finding out how many are left, or what the difference is. There are lots of different subtraction questions, so let's work through them together." },
  { file: 'audio/help-subtraction/scene-1-take-away.mp3',
    text: "Let's start with a simple one. 6 take away 4 is ? We start with 6 and remove 4. One, two, three, four taken away — there are now only 2 left. So 6 take away 4 equals 2. You might also see questions written like this: 11 minus 4, or solve this subtraction sum. They all mean the same thing — start with the big number and take it away. The answer is going to be a smaller number than the number you start with." },
  { file: 'audio/help-subtraction/scene-2-difference.mp3',
    text: "Some questions show two rows of objects and ask: what is the difference? There are more tractors in the top row than the bottom. To find the difference, line them up and count the extras. The top row has 7 and the bottom row has 4. 7 take away 4 equals 3. So the difference is 3. The word difference just means how many more one group has than the other." },
  { file: 'audio/help-subtraction/scene-3-word-problems.mp3',
    text: "Word problems tell a little story. The shopkeeper made 6 sandwiches and sold 2. How many does he have left? Find the numbers — 6 and 2. The words sold and left tell us to subtract. 6 take away 2 equals 4. Look for clue words like left, sold, ate, gave away, or how many remain. They all tell you it's a subtraction question." },
  { file: 'audio/help-subtraction/scene-4-missing-number.mp3',
    text: "Sometimes there's a missing number in the subtraction number sentence. 8 take away something equals 3. Think: I start at 8 and need to land on 3. Start at 8 and count back until you get to three — seven, six, five, four, three. That's 5 jumps, so the missing number is 5. The missing number might be at the start too — something take away 5 equals 3. If I start with 3 and add back the 5 I took away, what do I get? 3 plus 5 equals 8. So the missing number is 8. Remember: when the missing number is at the start, adding can help us find the answer to a subtraction question." },
  { file: 'audio/help-subtraction/scene-5-which-sum.mp3',
    text: "Some questions ask: which other sum equals this number? For example: what other sum equals 11? You'll see options like 14 minus 4, or 17 minus 6. Work each one out — 14 minus 4 is 10. No, this number sentence does not equal 11. 17 minus 6 is 11. Yes, this number sentence equals 11! So 17 minus 6 is the answer. You will need to solve each answer option until you find the one that matches." },
  { file: 'audio/help-subtraction/scene-6-subtracting-tens.mp3',
    text: "When you subtract a round number of tens, only the tens digit changes. 29 take away 10 — the tens digit drops from 2 to 1. The answer is 19. The ones digit stays at 9. 48 take away 20 — the tens digit drops from 4 to 2. The answer is 28. 91 take away 50 — the tens digit drops from 9 to 4. The answer is 41. The ones digit always stays the same when you subtract whole tens." },
  { file: 'audio/help-subtraction/scene-7-bigger-numbers.mp3',
    text: "Sometimes the subtraction questions use bigger numbers. We can use what we know about tens and ones to help us. Let's try 35 take away 12. First, take away the 10. 35 take away 10 is 25. Now take away the 2 more. 25 take away 2 is 23. So 35 take away 12 equals 23. Sometimes a question might ask: what is the difference between two numbers? Difference means how much bigger one number is than the other. Let's look at these two numbers. What is the difference between 25 and 20? Count on from 20 to 25. 21, 22, 23, 24, 25. That's 5 more. So the difference between 25 and 20 is 5. When you see bigger numbers, use tens and ones to help you work it out." },
  { file: 'audio/help-subtraction/scene-8-number-sentence.mp3',
    text: "Some questions give you a story and ask which number sentence matches. Will baked 36 muffins. He took 23 to school. He had 13 left. Which number sentence represents this? He started with 36 and took away 23. That's 36 minus 23, or 36 take away 23. The clue is that some were taken away — that tells you it's subtraction, not addition or multiplication." },
  { file: 'audio/help-subtraction/scene-9-true-false.mp3',
    text: "Sometimes a question gives you an answer and asks if it is correct. 82 minus 19 equals 73. True or false? You will need to work this out yourself to check if this is right or wrong. Start at 82 on a number line. Jump back 10 to 72. Then jump back 9 more to 63. We landed on 63. The question says the answer is 73. 63 is not 73, so the answer is false. Always work it out yourself first, then compare your answer to the answer in the question." },
  { file: 'audio/help-subtraction/scene-10-outro.mp3',
    text: "Now it's your turn! Try some subtraction questions yourself." },
];

// ==========================================
// HELP - COUNTING
// ==========================================
const helpCountingAudio = [
  { file: 'audio/help-counting/scene-0-intro.mp3',
    text: "Hello! Today we're practising counting. Counting means finding out how many there are. You'll see pictures of objects, dots, ten-frames, and blocks — and your job is to count them up. Let's look at the different types of counting questions." },
  { file: 'audio/help-counting/scene-1-counting-objects.mp3',
    text: "The simplest counting question shows you some objects and asks how many. You might see questions that say: match the items to the correct number — 8 balls. Or how many blocks, how many eggs, how many butterflies. The trick is to count carefully — touch each one as you go. Don't skip any, and don't count any twice. Here are some balls. One, two, three, four, five, six, seven, eight. There are 8 balls. The last number you say is always the answer." },
  { file: 'audio/help-counting/scene-2-ten-frames.mp3',
    text: "Ten-frames make counting bigger numbers much easier. Each full ten-frame has 10 dots. To count, start by counting the full frames in tens — 10, 20, 30, 40, 50, 60. Then count on the extra dots in the last frame — 61, 62. So there are 62 dots. If a question says how many dots altogether, look for ten-frames and count them this way. Full frames first in tens, then count on the extras." },
  { file: 'audio/help-counting/scene-3-match-to-amount.mp3',
    text: "Some questions show objects grouped in tens — like pop sticks bundled together. Match the items to the correct amount. First, count the bundles of ten — four bundles is 40 because there is 10 in each bundle. Then count the loose ones — 6 more. 40 plus 6 is 46. The bigger the number, the more important it is to use an efficient strategy and count in groups rather than one by one." },
  { file: 'audio/help-counting/scene-4-hundreds.mp3',
    text: "For really big numbers, you'll see hundreds blocks too. Which answer shows 112 blocks? Look for 1 hundred, 1 ten, and 2 ones. That's 100 plus 10 plus 2, which is 112. Sometimes the question uses shapes instead — a circle means 100, a square means 10, a triangle means 1. Which answer represents 262? 2 circles, 6 squares, and 2 triangles — that's 200 plus 60 plus 2. Count the hundreds first, then the tens, then the ones." },
  { file: 'audio/help-counting/scene-5-reading-picture.mp3',
    text: "Some questions show a picture with different people and their objects. Who has 31 balls? You need to count each person's group carefully. Jess has 35, Tom has 31, Anna has 25. Tom has 31 — that's the answer. You might also be asked how many does Jess have, or how many altogether. If you see the word altogether, then you need to add the groups together to find the total amount altogether." },
  { file: 'audio/help-counting/scene-6-true-false.mp3',
    text: "A true or false counting question gives you a number and a picture. There are 45 leaves. True or false? Count the leaves yourself to check. If you count 45, it's true. If you get a different number, it's false. Here's another one — if there are 6 full ten-frames and one with 8 dots, there would be 68 dots. 6 full frames is 60, plus 8 is 68. That's true! Always count carefully before you answer." },
  { file: 'audio/help-counting/scene-7-outro.mp3',
    text: "Now it's your turn! Try some counting questions yourself." },
];

// ==========================================
// HELP - ORDINAL NUMBERS
// ==========================================
const helpOrdinalNumbersAudio = [
  { file: 'audio/help-ordinal-numbers/scene-0-intro.mp3',
    text: "Hello! Today we're learning about ordinal numbers. Ordinal numbers tell us the position or order of something. Instead of how many, they tell us which one — like first, second, or third. Let's find out how they work." },
  { file: 'audio/help-ordinal-numbers/scene-1-what-are-ordinals.mp3',
    text: "Ordinary numbers like 1, 2, 3 tell us how many. Ordinal numbers tell us what position something is in. First, second, third, fourth, fifth — these are ordinal numbers. We write them with special endings: 1st, 2nd, 3rd, 4th, 5th. They tell us the order — who came first, who came second, and so on." },
  { file: 'audio/help-ordinal-numbers/scene-2-to-twenty.mp3',
    text: "Let's learn the ordinal numbers from first to twentieth. First is written 1st. Second is written 2nd. Third is written 3rd. After that, most of them end in T-H. Fourth, fifth, sixth, seventh, eighth, ninth, tenth. Eleventh, twelfth — twelfth is a tricky one! Thirteenth, fourteenth, fifteenth. Sixteenth, seventeenth, eighteenth, nineteenth, twentieth. Look closely at the spelling of these ones: first, second, third, fifth, eighth, ninth, and twelfth — they don't follow the usual pattern of just adding T-H at the end." },
  { file: 'audio/help-ordinal-numbers/scene-3-race.mp3',
    text: "Many questions show a race and ask about positions. The race had 6 entries. What position did Ben finish in? Look at the picture — count from the front. The one at the very front is 1st. The next one is 2nd, then 3rd, then 4th, and so on. If Ben is at the front, he finished 1st. Always count from the start of the race — the leader is 1st." },
  { file: 'audio/help-ordinal-numbers/scene-4-front-behind.mp3',
    text: "Some questions ask how many finished in front of or behind someone. Josh finished 3rd. How many finished in front of Josh? If Josh is 3rd, then 1st and 2nd are in front of him — that's 2. How many finished behind Josh? If there were 6 in the race and Josh is 3rd, then 4th, 5th, and 6th are behind him — that's 3. In front means a lower position number. Behind means a higher position number." },
  { file: 'audio/help-ordinal-numbers/scene-5-true-false.mp3',
    text: "True or false questions test what you know about ordinal order. The third student in a line is before the fifth student. True or false? Third comes before fifth — 3rd, 4th, 5th. That's true! First is the ordinal number for 1. True or false? Yes! 1st means first. That's true! Twelfth is the ordinal number for 20. True or false? No — twelfth is 12th, not 20th. Twentieth is the ordinal number for 20. That's false!" },
  { file: 'audio/help-ordinal-numbers/scene-6-outro.mp3',
    text: "Now it's your turn! Try some ordinal number questions yourself." },
];

// ==========================================
// HELP - TELLING THE TIME
// ==========================================
const helpTellingTimeAudio = [
  { file: 'audio/help-telling-time/scene-0-intro.mp3',
    text: "Hello! Today we're learning about telling the time. We use clocks to know what time it is. We use calendars to know what year, month or day it is. Let's look at the different types of time questions." },
  { file: 'audio/help-telling-time/scene-1-oclock.mp3',
    text: "When the long hand points straight up to 12, it's an o'clock time. The short hand tells us the hour. If the short hand points to 3 and the long hand points to 12, it's 3 o'clock. If the short hand points to 9, it's 9 o'clock. Remember: the short hand is the hour hand, and the long hand is the minute hand." },
  { file: 'audio/help-telling-time/scene-2-half-past.mp3',
    text: "When the long hand points straight down to 6, it's half past. Half past means 30 minutes past the hour. If the short hand is between 3 and 4, and the long hand points to 6, it's half past 3. We can also write it as 3:30. Notice the short hand moves a little bit past the hour — it's halfway between 3 and 4." },
  { file: 'audio/help-telling-time/scene-3-quarter.mp3',
    text: "When the long hand points to 3, it's quarter past. Quarter past means 15 minutes past the hour. So if the short hand is just past 2, and the long hand is on 3, it's quarter past 2. When the long hand points to 9, it's quarter to the next hour. Quarter to means 15 minutes before the next hour. If the long hand is on 9 and the short hand is almost at 5, it's quarter to 5." },
  { file: 'audio/help-telling-time/scene-4-days.mp3',
    text: "There are 7 days in a week. Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday. If today is Tuesday, tomorrow is Wednesday. If today is Saturday, yesterday was Friday. To answer these questions you need to know the order of the days of the week." },
  { file: 'audio/help-telling-time/scene-5-months.mp3',
    text: "There are 12 months in a year. January, February, March, April, May, June, July, August, September, October, November, December. What month comes after April? May! What month comes before July? June! January is the first month at the beginning of the year. December is the last month at the end of the year. A question might ask you which month is the third month — that's March." },
  { file: 'audio/help-telling-time/scene-6-calendar.mp3',
    text: "A calendar shows you all the days in a month. To find what day of the week a date falls on, find the date number and look up to the top of that column. What day of the week is the 5th of May? Find 5 on the calendar, look up — it's a Monday. Some questions ask what day is 2 days before or 3 days after a date. Just count forwards or backwards on the calendar from that date." },
  { file: 'audio/help-telling-time/scene-7-outro.mp3',
    text: "Now it's your turn! Try some time and calendar questions yourself." },
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
  'help-partitioning': helpPartitioningAudio,
  'help-addition-scenes': helpAdditionScenesAudio,
  'help-homophones': helpHomophonesAudio,
  'help-subtraction': helpSubtractionAudio,
  'help-counting': helpCountingAudio,
  'help-ordinal-numbers': helpOrdinalNumbersAudio,
  'help-telling-time': helpTellingTimeAudio,
};

async function generateAudioWithTimestamps(text, outputPath, speed = 0.9) {
  console.log(`Generating (with timestamps): ${outputPath}`);

  try {
    const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}/with-timestamps`, {
      method: 'POST',
      headers: {
        'xi-api-key': API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: text,
        model_id: 'eleven_multilingual_v2',
        output_format: 'mp3_44100_128',
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
          speed: speed
        }
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    const data = await response.json();

    // Save audio (base64 encoded)
    const audioBuffer = Buffer.from(data.audio_base64, 'base64');
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(outputPath, audioBuffer);
    console.log(`  ✓ Audio saved: ${outputPath}`);

    // Save alignment/timestamps
    const transcriptPath = outputPath.replace('.mp3', '.json');
    const transcriptDir = path.join(path.dirname(outputPath), 'transcripts');
    if (!fs.existsSync(transcriptDir)) {
      fs.mkdirSync(transcriptDir, { recursive: true });
    }
    const transcriptFile = path.join(transcriptDir, path.basename(transcriptPath));
    fs.writeFileSync(transcriptFile, JSON.stringify(data.alignment, null, 2));
    console.log(`  ✓ Timestamps saved: ${transcriptFile}`);

    await new Promise(r => setTimeout(r, 500));

  } catch (error) {
    console.error(`  ✗ Failed: ${outputPath} - ${error.message}`);
  }
}

async function main() {
  // Get template and optional filter from command line args
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const template = args[0];
  const filter = args[1]; // Optional: filter to specific files (e.g., "question", "help")

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

  // Use --timestamps flag for word-level timing data
  const useTimestamps = process.argv.includes('--timestamps');

  for (const item of audioToGenerate) {
    const speed = item.speed || 0.9;
    if (useTimestamps) {
      await generateAudioWithTimestamps(item.text, item.file, speed);
    } else {
      await generateAudio(item.text, item.file, speed);
    }
  }

  console.log('');
  console.log('='.repeat(50));
  console.log('Done!');
  console.log('='.repeat(50));
}

main();
