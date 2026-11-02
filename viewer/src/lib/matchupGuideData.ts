// Original editorial guides, not combat-model output or inferred replay state.
export const GUIDE_VERSION=1;
export const REFERENCE_BUILD=185872;
export const REFERENCE_COMMIT='3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f';
export type Guide={id:string;headline:string;expect:string;army:[string,string,string];position:string;watch:string;why:string;cue:string;sources:string[]};
const common={
 position:'Separate the army problem from the building problem. Protect workable resources first; bring protected siege when a fortified position must actually be removed. A good unit matchup is not permission to fight under defensive buildings.',
 watch:'Check the supporting units, upgrades, numbers and terrain before taking the fight. Availability in a tree does not mean you could afford, complete or safely use an option.',
 sources:['trees/FRANKS.json','strings.en.json']
};
export const FRANKS_GUIDES:Record<string,Guide>={
 Sicilians:{...common,id:'franks-sicilians-v1',headline:'Stop the foothold, not just the infantry.',
  expect:'If they choose Serjeants and Donjons, treat it as a reinforcing position as well as an army. Serjeants can build Donjons; Donjons can train more Serjeants. Sicilians also have cavalry options: the civilization alone does not identify their army.',
  army:[
   'If Serjeants are pressuring you: protect local resources, make small defensive walls where useful, and let ranged units fire from safety. A few Archers chip armoured infantry down slowly; do not chase underneath a Donjon.',
   'Against mostly Serjeants, consider upgraded Knights kept together, or protected Scorpions behind a screen. Monks may help against small groups, but require safety; Sicilian conversion-resistance research is a further consideration. Check for Pikemen before committing cavalry.',
   'Against an infantry-heavy army, protected Hand Cannoneers are an option after Chemistry. Keep a frontline; do not let infantry surround the gunners. If the composition changes, reassess rather than massing a counter to yesterday’s army.'
  ],
  position:'Do not repeatedly clear a few Serjeants and leave their production foothold untouched. First secure usable resources; then compare bypassing the Donjons with removing them using protected siege. A Donjon placement request is not proof it was completed.',
  watch:'Pikemen change the Knight decision. Sicilian bonus-damage resistance makes bonus-based counters less decisive, not useless. Hauberk can strengthen their Knight line later; First Crusade can add Serjeants and conversion resistance. These are reference capabilities, not observed research.',
  why:'Armour can make small ranged groups feel ineffective, while forward production keeps replacing the pressure. That can feel awkward even in a win. Your replay inputs alone cannot establish that this is what actually caused the pressure.',
  cue:'Before reinforcing into the same position, ask: am I solving the army, the production foothold, or neither?',
  sources:['trees/FRANKS.json','trees/SICILIANS.json','strings.en.json:26538,26540,26544,120186']},
 Britons:{...common,id:'franks-britons-v1',headline:'Make the ranged army move.',
  expect:'If Britons choose foot Archers, their later-age range can make a direct approach costly. Do not infer a ranged army simply from the civilization.',
  army:['Against an actual Archer group, compare mobile pressure elsewhere with Skirmisher support. Keep supporting units together and check what can safely defend your resources.','Knights need a safe way to reach the ranged army. Compare an approach from another direction with Skirmisher or protected siege support; terrain and supporting Pikemen can change the choice.','If the ranged mass remains the problem, compare Elite Skirmishers and protected siege with your cavalry’s job. Do not feed separate reinforcements through the same firing lane.'],
  why:'Range and a protected concentration can make a seemingly suitable cavalry army struggle to connect. The missing ingredient may be an approach or a different target, not simply another Stable.',
  cue:'Before charging a ranged mass, name the route that actually lets your army reach it.',sources:['trees/FRANKS.json','trees/BRITONS.json','strings.en.json:120150']},
 Bohemians:{...common,id:'franks-bohemians-v1',headline:'Check the screen before sending Knights.',
  expect:'Bohemians have a stronger spear-line bonus and can access Chemistry and Hand Cannoneers in Castle Age in this reference. Neither capability proves those units were fielded.',
  army:['If Spears are protecting their army, keep Scouts away from that concentration. Consider available ranged support or a different target rather than forcing a cavalry fight.','Check the actual mix: spear-heavy protection, ranged units and gunpowder ask different questions. Compare ranged or protected siege support with keeping Knights mobile elsewhere.','Do not solve every protected group by adding more cavalry. Identify the screen, the damage-dealing units and the siege separately, and protect the support you choose.'],
  why:'A familiar-looking spear screen can punish cavalry more than expected, while Castle-age gunpowder can arrive earlier than a generic Imperial-age assumption.',
  cue:'Identify what protects the enemy’s damage dealers before choosing your cavalry’s target.',sources:['trees/FRANKS.json','trees/BOHEMIANS.json','strings.en.json']},
 Berbers:{...common,id:'franks-berbers-v1',headline:'Identify the Stable mix, not just the Stable.',
  expect:'Berber Stable discounts can support repeated cavalry investment. Camel, Knight and light-cavalry compositions still require different responses; a discount is not an observed spending total.',
  army:['Scout what the first cavalry group is doing. Protect exposed workers and compare local spear support with keeping your own Scouts mobile.','Against mostly Knights, compare spear support and safe engagements. Against Camels, do not blindly take a cavalry mirror; consider supporting damage or another target. Check numbers and upgrades.','Keep checking the mix as reinforcements arrive. A supporting unit or a different route may address the problem better than matching every opposing queue input.'],
  why:'Similar-looking queue activity need not represent similar investment, and the same production building can supply units with quite different jobs.',
  cue:'Before matching cavalry production, identify whether you are answering Knights, Camels or raids.',sources:['trees/FRANKS.json','trees/BERBERS.json','strings.en.json']}
};
export const GENERAL_GUIDE:Guide={...common,id:'general-land-review-v1',headline:'Read the army, then choose the job.',
 expect:'There is no authored civilization-pair guide for this selection yet. Use the recorded inputs as prompts for what to inspect—not proof of a fielded army or a generic “wrong counter” verdict.',
 army:['First identify what threatens workers or resource access. Compare local protection, moving workers and an available response you can sustain; do not open every military line at once.','Identify the enemy’s damage dealers and supporting screen. Compare keeping your current response, adding support, changing composition or avoiding the concentration.','Recheck the mix and your objective. Protect any siege or ranged support you add, and distinguish destroying an army from removing its production or defensive position.'],
 why:'The same composition can keep being useful if its production, access or supporting position survives. Repeated pressure does not by itself establish poor trades, and winning does not prove every decision was efficient.',
 cue:'Before the next commitment, name the threat, your current response’s job, and what would make you adapt.',sources:[]};
