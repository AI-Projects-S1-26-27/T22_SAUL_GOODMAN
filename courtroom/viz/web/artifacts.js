/* What each exhibit actually looks like when it's handed up: the note, the text message, the receipt,
 * the camera still. Witnesses are not here (they walk to the stand instead).
 * Each entry has a `type` that picks a renderer in app.js:
 *   note, sms, receipt, log, cctv, photo, doc, ledger, ad, chat
 * Every name, number and message is made up for these fictional cases.
 */
"use strict";

window.ARTIFACTS = {
  /* ---------------------------------------------------------------- The Missing Cookies */
  "P-CRUMBS": { type: "photo", scene: "shirt", caption: "Sam's school shirt, 1:05 pm" },
  "P-CAMERA": { type: "cctv", cam: "HALLWAY CAM 2", time: "12:41:07", scene: "kid", caption: "A child in a red jacket outside the kitchen door" },
  "D-SNACK": { type: "note", text: "Sam, I packed 4 chocolate chip cookies in your lunchbox. Don't eat them all before lunch! Love, Mum x" },
  "D-CONTEST": { type: "ledger", title: "Year 5 Spelling Contest: results", rows: [["1st", "Sam"], ["2nd", "Maya"], ["3rd", "Leo"]], foot: "Held last Friday in the school hall" },

  /* ---------------------------------------------------------------- The Broken Bike */
  "P-PHOTO": { type: "photo", scene: "bike", caption: "Ana's bike, Saturday 9:12 am. Straight wheel." },
  "P-TEXT": { type: "sms", contact: "Raj (neighbour)", time: "Saturday 6:48 pm", msgs: [["them", "hey Ana, back from the ride"], ["them", "sorry, I hit a curb near the park"], ["me", "what?? is the bike ok?"]] },
  "P-RECEIPT": { type: "receipt", shop: "Spoke & Wheel Bike Repair", date: "Monday", lines: [["Front wheel 26in", "72.00"], ["Fitting and labour", "18.00"]], total: "90.00" },
  "D-OLD": { type: "ad", title: "FOR SALE: City bike, blue", price: "$140", text: "Used bike, rides well. Small wheel issue, needs a tune-up. Collection only." },
  "D-FRIENDSHIP": { type: "photo", scene: "friends", caption: "Leo and Raj, beach trip last summer" },

  /* ---------------------------------------------------------------- The Dug-Up Garden */
  "P-PAWS": { type: "photo", scene: "paws", caption: "Paw prints from the tomato bed to the fence" },
  "P-GATE": { type: "photo", scene: "gate", caption: "Rex's gate, 7:30 am. Wide open." },
  "D-LOCK": { type: "log", title: "GateGuard smart lock: back gate", rows: [["20:58", "Locked (keypad)"], ["21:00 to 06:59", "No activity"], ["07:02", "Unlocked (owner's phone)"], ["07:03", "Gate opened"]], mark: 1 },
  "D-COMPLAINTS": { type: "ledger", title: "Mrs. Green's letters to the council", rows: [["March", "Rex barking"], ["April", "Rex barking again"], ["May", "Dog hair on my car"], ["June", "Rex looked at my cat"], ["July", "Rex is a menace"]] },

  /* ---------------------------------------------------------------- Helix trade secrets */
  "P-VPN": { type: "log", title: "Helix VPN gateway", rows: [["02:09:14", "LOGIN avance (Adrian Vance)"], ["02:09:15", "Source: 81.2.69.160"], ["02:31:40", "LOGOUT avance"]], mark: 0 },
  "P-BADGE": { type: "log", title: "Door access: Lab B", rows: [["01:58:40", "Garage barrier: car HX-4471"], ["02:02:11", "Badge #0442 Vance, A. ACCEPTED"], ["02:44:03", "Door closed"]], mark: 1 },
  "P-DLP": { type: "log", title: "Security alert: data leaving the company", rows: [["02:14", "Upload started: drive.personal-cloud.com"], ["02:27", "4.2 GB sent"], ["!", "Export missing its security certificate"]], mark: 1 },
  "P-LAPTOP": { type: "log", title: "Police copy of Vance's laptop", rows: [["/Downloads/", "tessellate_floorplan_v7.gds"], ["/Downloads/", "tessellate_timing.xlsx"], ["Note", "Searched one day after the warrant expired"]], mark: 0 },
  "P-EMAILS": { type: "doc", head: "From: talent@quorvex.example", title: "Re: your next move", lines: ["Adrian, great talking last week.", "We can offer a signing bonus for any IP you bring with you.", "Let's keep this between us for now."], sign: "M. Hale, Quorvex Recruiting" },
  "P-CRYPTO": { type: "ledger", title: "Wallet 0x7f3…c21: incoming", rows: [["12 days after the leak", "+ 40,000 USDC"], ["From", "unknown wallet"]] },
  "P-CCTV": { type: "cctv", cam: "HELIX GARAGE CAM 1", time: "01:50:22", scene: "car", caption: "Grey hatchback, plate HX-4471, enters the garage" },
  "D-ROUTER": { type: "log", title: "Vance home router", rows: [["02:10", "Adrian's phone: online at home"], ["02:10", "Adrian's laptop: online at home"], ["02:10", "Living room TV: asleep"]], mark: 0 },
  "D-PHISH": { type: "doc", head: "Helix IT Security, internal", title: "Warning: passwords stolen", lines: ["In March, a fake login email fooled several staff.", "Some passwords and service accounts were stolen.", "Not all of them have been changed yet."], sign: "Helix IT Security Team" },
  "D-REVIEW": { type: "doc", head: "Helix HR: formal complaint", title: "Complaint by P. Nandakumar", lines: ["About: Adrian Vance", "Reason: he was promoted over me unfairly.", "I want this reviewed."], sign: "Filed in January" },

  /* ---------------------------------------------------------------- Aurora crypto */
  "P-TXS": { type: "log", title: "Blockchain: attacker wallet 0xa1…", rows: [["0xa1", "Borrow 90M (flash loan)"], ["0xa4", "Push the price feed up"], ["0xa7", "Withdraw 31M from Aurora"], ["0xa9", "Repay loan, keep 31M"]], mark: 2 },
  "P-TXS-DUP": { type: "doc", head: "Printed from a public block explorer", title: "Same transactions, 0xa1 to 0xa9", lines: ["Status: success", "Value moved: 31,000,000 USD", "Printed by the police the next day"], sign: "" },
  "P-SEED": { type: "note", text: "orbit  maple  rescue  velvet  cinema  gather  lunar  twelve  oxygen  fabric  noble  quiet" },
  "P-KYC": { type: "doc", head: "Exchange ID check (KYC)", title: "Account #55120: verified", lines: ["Name on account: the accused", "ID: passport, checked", "This account funded the attack wallet"], sign: "Shared only on the day of trial" },
  "P-MIXER": { type: "ledger", title: "Money sent into a mixer", rows: [["Day 1", "3,000,000 USD"], ["Day 2", "4,000,000 USD"], ["Day 3", "2,000,000 USD"]], foot: "Total hidden: 9,000,000 USD" },
  "P-CHAT": { type: "sms", contact: "nyx.eth (group chat)", time: "03:12 am", msgs: [["them", "it worked"], ["them", "time to retire lol"]] },
  "D-BOUNTY": { type: "doc", head: "Aurora Protocol: official rules", title: "Bug bounty policy", lines: ["Found a bug? Move the funds somewhere safe.", "Tell us within 72 hours and return them.", "You may keep 10% as a reward."], sign: "Aurora core team" },
  "D-RETURN": { type: "log", title: "Blockchain: Aurora safe wallet", rows: [["48 hours later", "+ 22,000,000 USD received"], ["From", "the attacker wallet"]], mark: 0 },
  "D-DEVBIAS": { type: "ledger", title: "Kofi Mensah's Aurora account", rows: [["Before the attack", "120,000 USD"], ["After the attack", "0 USD"]], foot: "He lost all his savings" },

  /* ---------------------------------------------------------------- Kestrel robotaxi */
  "P-BUGS": { type: "doc", head: "Kestrel bug tracker, ticket #4471", title: "Bikes lost at dusk", lines: ["The car stops seeing bicycles when it gets dark.", "Spotted only 71% of bikes in tests.", "Status: WON'T FIX"], sign: "Closed by: Product team" },
  "P-BILLS": { type: "receipt", shop: "St. Vale General Hospital", date: "14 weeks of care", lines: [["Surgery", "98,000.00"], ["Hospital stay", "52,000.00"], ["Physical therapy", "36,000.00"]], total: "186,000.00" },
  "P-FORUM": { type: "chat", site: "carforum.example", user: "anon_4471", text: "these AV-7 robotaxis literally cannot see bikes. trust me." },
  "D-TELEM": { type: "log", title: "AV-7 car data, crash night", rows: [["19:42:03.1", "Cyclist detected"], ["19:42:03.6", "Braking started"], ["19:42:04.7", "Impact"]], mark: 0 },
  "D-NHTSA": { type: "doc", head: "Road Safety Board", title: "Safety check: passed", lines: ["Vehicle: Kestrel AV-7", "Software tested: detecting people and bikes", "Result: meets the rules"], sign: "Inspector R. Banks" },
  "D-TERM": { type: "doc", head: "Kestrel Mobility HR", title: "Letter of dismissal", lines: ["To: Dr. Aiko Tan", "You are dismissed for copying company data", "to a personal drive."], sign: "Kestrel HR" },
  "D-HELMET": { type: "photo", scene: "helmet", caption: "Scene photo: the cyclist's helmet was still on the bike" },

  /* ---------------------------------------------------------------- Tricky tests */
  "P-WIRE": { type: "doc", head: "Phone recording (no warrant)", title: "Transcript, 11:02 pm", lines: ["Caller 1: is the package ready?", "Caller 2: it goes out tonight.", "Recorded without a judge's permission"], sign: "" },
  "P-DRIVE": { type: "photo", scene: "drive", caption: "Hard drive taken in the same illegal search" },
  "P-NOTE": { type: "note", text: "YOUR FILES ARE LOCKED. Pay 50 coins to get them back. You have 3 days." },
  "P-WALLET": { type: "ledger", title: "Ransom wallet payments", rows: [["Victim 1", "20 coins"], ["Victim 2", "30 coins"]], foot: "Handed over on the morning of the trial" },
  "D-ALIBI": { type: "doc", head: "Brokerage: automatic trading plan", title: "Plan set up in January", lines: ["Buy 500 shares on the 1st of every month.", "Runs automatically. Can't be changed by hand."], sign: "Signed: J. Park" },
  "P-WEAK": { type: "ledger", title: "Ms. Park's calendar", rows: [["Mon", "Dentist"], ["Wed", "Team lunch"], ["Fri", "Yoga"]] },
};
