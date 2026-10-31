/* The script for each case: what the lawyers say when they open, show each exhibit and close.
 * The trial engine decides *what happens* (which exhibit, which objection, how the judge rules);
 * this file only gives the people in the courtroom their words. Plain language throughout.
 *
 * Per case:
 *   points: plain names for the points the Accuser must prove (overrides legal jargon)
 *   open / close: opening statements and closing arguments, one per side
 *   ev[id].say: what the lawyer says when handing the exhibit up
 *   ev[id].short: how everyone refers to it afterwards ("the hallway video")
 *   ev[id].witness / wit: for testimony, who walks up to the stand and what they say there
 */
"use strict";

window.STORY = {
  "cookie-jar": {
    open: {
      prosecution: "Your Honour, at lunchtime a whole jar of cookies disappeared from the school kitchen. We will show that Sam was there, and that Sam took them.",
      defense: "Your Honour, Sam was nowhere near that kitchen. He spent his whole lunch in the library, with a book and his own cookies from home.",
    },
    close: {
      prosecution: "A witness saw him, a camera caught a kid near the kitchen, and there were crumbs on his shirt. Put it together, Your Honour.",
      defense: "Crumbs are not a crime. Sam had his own cookies, and the librarian watched him all lunch. There is real doubt here.",
    },
    ev: {
      "P-MAYA": { short: "Maya's story", say: "The Accuser calls Maya, a classmate of Sam's. Maya, tell the court what you saw at lunchtime.", witness: "Maya, classmate", wit: "I was walking to the playground and I saw Sam go into the kitchen. I'm sure it was him." },
      "P-CRUMBS": { short: "the crumbs on Sam's shirt", say: "When a teacher found Sam after lunch, his shirt was covered in cookie crumbs." },
      "P-CAMERA": { short: "the hallway video", say: "The hallway camera shows a kid in a red jacket right by the kitchen door. Sam wears a red jacket." },
      "P-RUMOR": { short: "what Mrs. Bell heard", say: "The Accuser calls Mrs. Bell, the school cook. Mrs. Bell, what were you told?", witness: "Mrs. Bell, school cook", wit: "A student came up to me after lunch and said: it was Sam, Sam took the cookies. I didn't see it myself." },
      "D-LIBRARIAN": { short: "the librarian's account", say: "The Defender calls Mr. Ortiz, the school librarian. Where was Sam at lunchtime?", witness: "Mr. Ortiz, librarian", wit: "Sam was in my library the whole lunch break, reading a dinosaur book at the front table. I could see him the entire time." },
      "D-SNACK": { short: "the lunch note", say: "Here is a note from Sam's mum. She packed cookies in his own lunchbox that day. That explains the crumbs." },
      "D-CONTEST": { short: "the spelling contest results", say: "These are last week's spelling contest results. Sam beat Maya. She might not be the fairest witness." },
    },
  },

  "broken-bike": {
    open: {
      prosecution: "Your Honour, Ana lent Raj her new bike for one afternoon. It came back with a bent wheel, and she had to pay to fix it. Raj should pay.",
      defense: "Your Honour, that wheel was wobbly before Raj ever touched it. You can't blame him for damage that was already there.",
    },
    close: {
      prosecution: "The wheel was straight that morning. Raj even texted to say sorry. And the repair cost ninety dollars. He should pay it back.",
      defense: "The bike was second-hand, with a known wheel problem. Raj's friend saw it wobble before the ride. That's not Raj's fault.",
    },
    ev: {
      "P-PHOTO": { short: "the morning photo", say: "This photo was taken the morning Raj borrowed the bike. Look closely. The wheel is perfectly straight." },
      "P-TEXT": { short: "Raj's text", say: "That evening, Raj sent Ana this text. It says: sorry, I hit a curb." },
      "P-RECEIPT": { short: "the repair receipt", say: "Here's the bike shop receipt. A new wheel cost ninety dollars." },
      "P-MECHANIC": { short: "the mechanic's opinion", say: "The Accuser calls Kim, the mechanic who fixed the bike. Kim, what bent that wheel?", witness: "Kim, bike mechanic", wit: "A slow wobble doesn't do this. This wheel hit something hard, like a curb, at speed." },
      "D-WOBBLE": { short: "Leo's account", say: "The Defender calls Leo, who was there when Raj picked up the bike. Leo, what did you notice?", witness: "Leo, Raj's friend", wit: "When Raj wheeled it out of Ana's garage, the front wheel was already wobbling. I said so at the time." },
      "D-OLD": { short: "the old sale ad", say: "This is the ad Ana bought the bike from. It says: used bike, small wheel issue." },
      "D-FRIENDSHIP": { short: "the holiday photo", say: "I'll be honest with the court. Here's a photo of Leo and Raj on holiday. Yes, they're good friends." },
    },
  },

  "garden-dog": {
    open: {
      prosecution: "Your Honour, Mrs. Green's tomato garden was dug up overnight. The paw prints lead straight to the fence next door, where Rex the dog lives.",
      defense: "Your Honour, Rex spent the night locked in his own yard. Something dug up that garden, but it wasn't him.",
    },
    close: {
      prosecution: "Paw prints, barking in the night, a gate left open. Rex had the chance, and the owner gave it to him.",
      defense: "The gate was locked all night, and a vet says those prints are far too small for Rex. It was a raccoon, Your Honour.",
    },
    ev: {
      "P-PAWS": { short: "the paw prints", say: "Muddy paw prints run from the dug-up tomatoes all the way to the fence." },
      "P-GATE": { short: "the gate photo", say: "This photo was taken the next morning. The gate to Rex's yard is wide open." },
      "P-GREEN": { short: "Mrs. Green's account", say: "The Accuser calls Mrs. Green herself. Mrs. Green, what did you hear that night?", witness: "Mrs. Green, garden owner", wit: "Around midnight I heard barking right outside my bedroom window, in my garden. Loud barking." },
      "P-RACCOON": { short: "the cousin's claim", say: "Mrs. Green, did anyone else tell you about Rex?", witness: "Mrs. Green, garden owner", wit: "My cousin told me that Rex digs holes all the time. Everybody knows it." },
      "D-LOCK": { short: "the smart-lock log", say: "The gate has a smart lock. Its log shows it stayed locked from nine at night until seven in the morning." },
      "D-VET": { short: "the vet's opinion", say: "The Defender calls Dr. Fox, a vet. Dr. Fox, you measured the paw prints. What did you find?", witness: "Dr. Fox, vet", wit: "The prints are about four centimetres wide. Rex's paws are nearly ten. And they have five long fingers. These are a raccoon's." },
      "D-COMPLAINTS": { short: "the old complaints", say: "Mrs. Green has complained about Rex five times before. She may have made up her mind already." },
    },
  },

  "helix-espionage": {
    points: { access: "Vance broke into the files", exfiltration: "The files were taken out", intent: "He meant to help a rival" },
    open: {
      prosecution: "Your Honour, at two in the morning someone copied Helix's secret chip design and sent it out. We will show it was Adrian Vance, and that he did it for money.",
      defense: "Your Honour, Adrian was asleep at home. His password was stolen in a phishing attack months ago. Someone used his account. Not him.",
    },
    close: {
      prosecution: "His badge, his login, his car in the garage, the upload, the money. Every road leads back to Adrian Vance.",
      defense: "A stolen password, an alarm that's wrong almost a third of the time, and a family who saw him at home. That is reasonable doubt.",
    },
    ev: {
      "P-VPN": { short: "the login record", say: "The company's login records show Vance's account connecting at nine minutes past two in the morning." },
      "P-BADGE": { short: "the badge record", say: "His security badge opened the door to Lab B at two minutes past two." },
      "P-DLP": { short: "the upload alarm", say: "A security alarm caught four gigabytes being uploaded to a personal cloud drive." },
      "P-LAPTOP": { short: "the laptop files", say: "Police searched his laptop and found the secret Tessellate design files on it." },
      "P-EXPERT": { short: "Dr. Marsh's analysis", say: "The Accuser calls Dr. Lena Marsh, a computer expert. Dr. Marsh, what was in that upload?", witness: "Dr. Lena Marsh, computer expert", wit: "The upload was 4.2 gigabytes. The secret Tessellate design archive is 4.2 gigabytes. That is not a coincidence." },
      "P-NANDA": { short: "Priya's account", say: "The Accuser calls Priya Nandakumar, Mr. Vance's co-worker. What did he tell you?", witness: "Priya Nandakumar, co-worker", wit: "A week before the leak, Adrian told me: Quorvex is going to make me rich. He was smiling when he said it." },
      "P-TIP": { short: "the informant's tip", say: "The Accuser calls Detective Samuel Okafor. Detective, what did your informant say?", witness: "Det. Samuel Okafor", wit: "My informant told me Vance was trying to sell the chip design. I can't say who the informant is." },
      "P-EMAILS": { short: "the recruiter emails", say: "These emails from a Quorvex recruiter promise him a special bonus for bringing secrets." },
      "P-CRYPTO": { short: "the crypto payment", say: "Twelve days later, forty thousand dollars in crypto landed in his account." },
      "P-CCTV": { short: "the garage video", say: "The office garage camera shows his car arriving at ten to two in the morning." },
      "D-SPOUSE": { short: "Mira's account", say: "The Defender calls Mira Vance, Adrian's wife. Where was your husband that night?", witness: "Mira Vance, wife", wit: "Adrian was asleep next to me all night. I woke up at two because the baby cried, and he was right there." },
      "D-ROUTER": { short: "the home router record", say: "Their home internet router shows his phone and laptop online at home at ten past two." },
      "D-PHISH": { short: "the phishing memo", say: "This company memo warns that staff passwords were stolen in a phishing attack in March." },
      "D-DLPEXPERT": { short: "Professor Cho's analysis", say: "The Defender calls Professor Ian Cho, a security expert. Professor, how reliable is that upload alarm?", witness: "Prof. Ian Cho, security expert", wit: "This alarm rule gets it wrong about three times in ten. It often flags normal backups as theft." },
      "D-HR": { short: "Mr. Reyes's guess", say: "The Defender calls Tom Reyes from HR. Mr. Reyes, what do you make of the upload?", witness: "Tom Reyes, HR manager", wit: "I think it was probably an approved personal backup. Staff do that all the time. But I didn't check myself." },
      "D-REVIEW": { short: "the complaint Priya filed", say: "Priya once filed a formal complaint against Adrian. She is not a neutral witness." },
      "D-CHARACTER": { short: "the neighbour's account", say: "The Defender calls Dana Whitfield, the Vances' neighbour. What kind of man is Adrian?", witness: "Dana Whitfield, neighbour", wit: "Adrian is a lovely neighbour. He mows his lawn every Sunday and helps everyone on the street." },
    },
  },

  "aurora-defi": {
    points: { control: "He controlled the wallet", execution: "That wallet took the money", fraud_intent: "He meant to keep it" },
    open: {
      prosecution: "Your Honour, thirty-one million dollars was drained from the Aurora crypto app in minutes. We will show the accused did it and meant to keep it.",
      defense: "Your Honour, my client found a hole in Aurora's code and moved the money to protect it, just like Aurora's own rules invite. Then he gave it back.",
    },
    close: {
      prosecution: "He hid nine million through a mixer and joked about retiring. That's not a rescue. That's a robbery.",
      defense: "He called the bounty desk within two hours and returned twenty-two million. Thieves don't give the money back.",
    },
    ev: {
      "P-TRACE": { short: "Rosa's money trail", say: "The Accuser calls Rosa Ibarra, a blockchain analyst. Ms. Ibarra, where did the attacker's money come from?", witness: "Rosa Ibarra, blockchain analyst", wit: "I followed the money backwards. The attacking wallet was funded straight from an exchange account in the accused's own name." },
      "P-TXS": { short: "the blockchain records", say: "These blockchain records show the attacking wallet draining the pool, step by step." },
      "P-TXS-DUP": { short: "the printout", say: "Here's a printout of those same transactions from a public website." },
      "P-SEED": { short: "the secret key", say: "Police found the wallet's secret recovery words written on paper in his flat." },
      "P-KYC": { short: "the exchange ID file", say: "The exchange's ID check links that funding account to the accused." },
      "P-MIXER": { short: "the mixer record", say: "Nine million dollars was pushed through a mixer, a tool that hides where money goes." },
      "P-DEV": { short: "Kofi's opinion", say: "The Accuser calls Kofi Mensah, an Aurora developer. Mr. Mensah, is this how friendly hackers behave?", witness: "Kofi Mensah, Aurora developer", wit: "No. Real white-hat hackers warn us first. Nobody honest drains thirty-one million dollars and hides part of it." },
      "P-CHAT": { short: "the chat message", say: "A chat message from that night says: time to retire, lol." },
      "D-BOUNTY": { short: "the bounty policy", say: "Aurora's own rules promise a ten percent reward to anyone who finds a bug and returns the funds." },
      "D-RETURN": { short: "the returned money", say: "Forty-eight hours later, twenty-two million dollars went straight back to Aurora." },
      "D-ZHAO": { short: "Lin Zhao's account", say: "The Defender calls Lin Zhao, who runs Aurora's bug-bounty desk. When did you hear from the accused?", witness: "Lin Zhao, bug-bounty desk", wit: "He messaged our desk less than two hours after the attack. He said he had the funds safe and wanted to return them." },
      "D-SHARED": { short: "the wallet-matching flaw", say: "The Defender calls Dr. Sam Ortega, a data scientist. Dr. Ortega, can we trust the method that linked those wallets?", witness: "Dr. Sam Ortega, data scientist", wit: "That wallet-matching method is wrong about one time in four. On its own, it can't tell you who owns a wallet." },
      "D-DEVBIAS": { short: "Kofi's losses", say: "Kofi Mensah lost his own savings in this attack. He has a reason to be angry." },
    },
  },

  "kestrel-av": {
    points: { defect: "The car's software was faulty", causation: "The fault caused the crash", damages: "The cyclist was really hurt" },
    open: {
      prosecution: "Your Honour, a self-driving taxi hit a cyclist in a crosswalk. The company knew its cars struggle to see bikes at dusk, and shipped them anyway.",
      defense: "Your Honour, our car saw the cyclist and braked. The cyclist rode through a red light. This was a tragic accident, not a faulty car.",
    },
    close: {
      prosecution: "A known bug marked won't fix, an engineer who warned them, and braking that came too late. The company is responsible.",
      defense: "The car detected the cyclist. A regulator checked the software. And a witness saw a red light. The fault was not ours.",
    },
    ev: {
      "P-EYE1": { short: "Grace's account", say: "The Accuser calls Grace Obi, who saw the crash. Ms. Obi, what colour was the light?", witness: "Grace Obi, eyewitness", wit: "I was waiting to cross. The walk sign was green for the cyclist. Then the taxi just kept coming." },
      "P-BUGS": { short: "the internal bug report", say: "This internal company report says the car loses track of bikes at dusk. It was marked: won't fix." },
      "P-TAN": { short: "Dr. Tan's account", say: "The Accuser calls Dr. Aiko Tan, a former engineer at the company. Dr. Tan, did they know about the problem?", witness: "Dr. Aiko Tan, former engineer", wit: "Yes. At dusk the car spotted only seventy-one percent of bikes. We told the managers. They shipped it anyway." },
      "P-RECON": { short: "the crash reconstruction", say: "The Accuser calls Dr. Ben Hollis, a crash expert. Dr. Hollis, when did the car brake?", witness: "Dr. Ben Hollis, crash expert", wit: "I rebuilt the crash from the skid marks and video. The car began braking nearly a second later than it should have." },
      "P-MED": { short: "the doctor's report", say: "The Accuser calls Dr. Ruth Adeyemi, who treated the cyclist. Doctor, how badly was he hurt?", witness: "Dr. Ruth Adeyemi, doctor", wit: "He had a broken pelvis. He needed surgery and fourteen weeks of physical therapy to walk properly again." },
      "P-BILLS": { short: "the medical bills", say: "The hospital bills come to one hundred and eighty-six thousand dollars." },
      "P-FORUM": { short: "the forum post", say: "Someone online posted that these cars can't see bikes." },
      "D-EYE2": { short: "Martin's account", say: "The Defender calls Martin Lund, who was in the next car. Mr. Lund, what did you see?", witness: "Martin Lund, driver", wit: "I was stopped right next to the crossing. The cyclist's light was red. He rode straight through it." },
      "D-TELEM": { short: "the car's data", say: "The car's own data shows it spotted the cyclist more than a second and a half before the crash." },
      "D-NHTSA": { short: "the safety check", say: "A safety regulator checked this software and passed it." },
      "D-TERM": { short: "Dr. Tan's firing record", say: "Dr. Tan was fired by the company for mishandling data. She may hold a grudge." },
      "D-HELMET": { short: "the helmet report", say: "The cyclist was not wearing a helmet, which made the injuries worse." },
    },
  },

  "edge-empty-docket": {
    points: { act: "Something wrong happened", identity: "The accused did it" },
    open: {
      prosecution: "Your Honour, we say the accused committed a cyber crime.",
      defense: "Your Honour, they have brought a case with no evidence at all. Let's see if they can prove anything.",
    },
    close: {
      prosecution: "We rest on what we've said.",
      defense: "Words aren't evidence, Your Honour. There's nothing here.",
    },
    ev: {},
  },

  "edge-mutual-exclusion": {
    points: { command: "Lark sent the bad command" },
    open: {
      prosecution: "Your Honour, a drone fleet went rogue after someone typed a bad command. We say it was Lark.",
      defense: "Your Honour, Lark was on a break. Someone else was at that keyboard.",
    },
    close: {
      prosecution: "Operator A saw Lark type it. That should settle it.",
      defense: "Operator B was actually at the console, and says it wasn't Lark. It's one word against another.",
    },
    ev: {
      "P-A": { short: "Operator A's account", say: "The Accuser calls Operator A. Who typed the command?", witness: "Operator A, shift operator", wit: "I watched Lark type that command. I was standing right behind the chair." },
      "D-B": { short: "Operator B's account", say: "The Defender calls Operator B. Where was Lark?", witness: "Operator B, shift operator", wit: "Lark was on a break. I was the one sitting at that console, and I didn't type it either." },
    },
  },

  "edge-poisoned-tree": {
    points: { deployment: "Kaur launched the attack", extortion: "Kaur demanded a ransom" },
    open: {
      prosecution: "Your Honour, a ransomware attack locked a company's computers and someone demanded money. We say that was Ms. Kaur.",
      defense: "Your Honour, every piece of their evidence was gathered the wrong way. Watch closely.",
    },
    close: {
      prosecution: "The recordings, the drive and the note all point to her.",
      defense: "Illegal recordings, an illegal search and a note nobody can vouch for. The rules exist for a reason.",
    },
    ev: {
      "P-WIRE": { short: "the phone recording", say: "We recorded her phone calls, where she talks about the attack software." },
      "P-DRIVE": { short: "the hard drive", say: "Police took a hard drive from her home that holds the attack software." },
      "P-NOTE": { short: "the ransom note", say: "This is the ransom note that appeared on the company's screens." },
      "P-INF": { short: "the informant's story", say: "The Accuser calls a paid informant. What do you know about the attack?", witness: "Paid informant", wit: "Someone told me Kaur did it. I don't remember who. I was paid for the tip." },
      "P-WALLET": { short: "the ransom wallet records", say: "These records show the ransom wallet's payments." },
    },
  },

  "edge-defense-only": {
    points: { trade: "Park traded on secret tips" },
    open: {
      prosecution: "Your Honour, we say Ms. Park bought shares using secret company news.",
      defense: "Your Honour, Ms. Park's trade was planned months in advance. Even the Accuser's own file shows it.",
    },
    close: {
      prosecution: "We leave it to the court.",
      defense: "There is no evidence of a secret tip. The trade was on autopilot.",
    },
    ev: {
      "D-ALIBI": { short: "the trading plan", say: "Ms. Park set up an automatic trading plan months earlier. This trade was part of it." },
      "P-WEAK": { short: "the calendar entry", say: "Here is a calendar entry from that week." },
    },
  },
};
