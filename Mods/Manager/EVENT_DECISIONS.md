# Naval Staff Briefings: event decisions

The active table contains 100 event groups: the game's original campaign
events plus the modern and Cold War additions. Each group now presents three
responses. The 26 groups that previously had only two usable responses have
received a third one.

## Showing consequences

Each question ends with its responses' effects, for example "Effects: (1)
Tension -1. (2) Budget +300, Tension +1. (3) Budget +100." The numbers follow
the answers from top to bottom. They are the Budget, Prestige and Tension
changes written to RTW3's event table; they are not a promise that every
campaign will value those outcomes the same way. A change of zero, or an empty
native field, is left out, and a response that changes nothing reads "no
change". A final phrase names documented special outcomes such as a build
order, peace talks, unrest, technology leakage or an army result. RTW3 still
applies those outcomes using its own event rules. Values 73 and 74 are shown as
native conditions because the installed condition list does not document what
they do. Hovering an answer still shows the game's own +/- hint.

The effects sit with the question because the answer buttons are a single
line (737, 849 and 737 pixels wide at 100% scaling) and cut off what does not
fit: with the effects added to the answers, 123 of the 300 lost their end once
XX/YY became a long nation name. The question wraps over five lines, and every
question with its effects needs at most four.

## Balance and clarity pass

- Added a distinct middle or conditional response to every two-choice event.
- Reworked identical responses in the Balkan fighting and hawkish-government
  events so their outcomes differ.
- Made public exposure of the port-visit scandal carry an explicit standing
  benefit and a larger tension cost; private leverage and confidentiality
  remain separate approaches.
- Made dismissing the domestic-unrest warning carry the native unrest effect;
  the other responses offer a modest cut or deeper cuts with social reform.
- Made private anti-piracy guards preserve funds at the cost of public credit.
- Made cancelling a nuclear-ship visit lower tension while losing standing.
- Separated canal rerouting from a more expensive international escort by
  giving them different cost and tension outcomes.

The response changes and added choices are declared in
`Mods/CampaignOverhaul/event_outcomes.json`. The event baseline is stored in
`Mods/CampaignOverhaul/event_mechanics_base.dat`. The renderer checks that all
100 question triggers and undeclared response effects still match that
baseline before producing the installed table.

The high-funds Parliament bill in event slot 46 is disabled by moving its
year window beyond the supported campaign era. This prevents the event from
cutting the naval budget in campaigns through 2050; its response records are
retained for compatibility.

## Limits

RTW3 provides three fixed response rows per event and a fixed set of numeric
effects and special-condition codes. This pass uses those native fields. It
does not add conditional follow-up dialogs, campaign-state-specific response
text, or new engine mechanics. Some historical outcomes therefore remain
approximations. Three answers can still lose their last words when XX or YY
becomes a very long nation name: two are the game's own text, one an older
reworded answer.
