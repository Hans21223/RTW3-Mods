# Historical Decolonization - Player and AI

The optional runtime mod adds dated, automatic self-government and independence
transfers without asking the player to accept or reject each scheduled outcome.
It applies the same rule to the player and every AI power.

For each listed territory, the mod checks the actual campaign year and current
owner. When the date arrives, it transfers the territory to **Neutral** only
if it is still held by one of the historical administering powers listed in
the schedule. A territory conquered or transferred to another power is left
alone. Existing later-start campaigns already past a release date are handled
on their next turn if they still have that colonial owner.

The game has no native nation slot for most of these newly independent states.
As in its own later-start maps, independence is represented by Neutral
ownership. The mod does not create a playable government, fleet, diplomacy or
country-specific economy. Neutral is also an approximation for outcomes that
the game cannot model directly, such as Newfoundland joining Canada or the
Vietnamese states emerging from the 1954 settlement.

The native rebellion routine can also trigger independence at random, including
for a nation's own core areas. The screenshot of Western USA becoming
independent is one such invalid outcome. The mod now blocks new random
rebellions in the game's core home regions and in territories with a scheduled
historical release. It also blocks the game's own transfers of a core home
region to Neutral, so a rebellion already under way cannot take one (before
1.1.1 this second guard let every game transfer through). Colonies are not
covered by it, because the game also hands possessions to Neutral after a war
and for Chinese concessions. The mod's own dated transfers are exempt. Native
upheaval events for other possessions remain active.

The mod does not model staged autonomy, referenda, negotiated treaties, or
armed struggles as separate mechanics because RTW3 has no corresponding
campaign states for them.

## Scheduled transfers

| Year | Possessions released |
| --- | --- |
| 1922 | Ireland |
| 1931 | Nova Scotia, New Brunswick, British Columbia, South Africa |
| 1942 | Western Australia, Eastern Australia |
| 1946 | The Philippines, Syria |
| 1947 | India, Pakistan, New Zealand |
| 1948 | Burma, Ceylon |
| 1949 | Newfoundland |
| 1951 | Libya |
| 1954 | Cochin China, Annam, Tonkin |
| 1956 | Egypt, Sudan, Tunisia, Morocco |
| 1957 | Malaya |
| 1960 | Cyprus, Nigeria, Somalia, Somaliland, Senegal, Cameroon, Middle Congo, Madagascar |
| 1961 | Sierra Leone, Tanganyika, Kuwait |
| 1962 | Algeria, Jamaica, Trinidad |
| 1963 | Kenya, Zanzibar |
| 1964 | Malta |
| 1965 | Singapore |
| 1967 | Yemen |
| 1971 | East Bengal, Trucial States |
| 1975 | Papua |
| 1977 | Djibouti |
| 1980 | New Hebrides |

The dates reflect several routes rather than one worldwide event: Irish
independence, Dominion constitutional autonomy, postwar Asian independence,
the 1950s and 1960s African and Caribbean waves, and later transfers. East
Bengal is dated to Bangladesh's independence in 1971, rather than to the 1947
partition that placed it in Pakistan. The game cannot represent Bangladesh or
the Tanganyika-Zanzibar union as a new playable country, so each relevant
possession becomes Neutral. Territories absent from RTW3's possession map
cannot be represented by this mod.

## Evidence and limits

The game update is session-only. It patches a reviewed call after the native
turn-event routine, the native rebellion entry, and the native ownership
transfer entry. The guard compares possession objects by the game's own name
lookup, only blocks transfer to Neutral, and allows the mod's dated release
processor through. It does not edit RTW3.exe or an existing save file directly.
Ownership changes become part of a campaign only when the player saves it.

The historical sequence follows the U.S. State Department's overview that
decolonization had multiple paths, including both negotiated transfers and
protracted revolutions, and the United Nations' territory/date records. The
game's Neutral-only country model means this implementation cannot simulate
every negotiated, partitioned or violent outcome in full.

- [U.S. Department of State: Decolonization of Asia and Africa, 1945-1960](https://history.state.gov/milestones/1945-1952/asia-and-africa)
- [U.S. Department of State: The South Asia Crisis and the Founding of Bangladesh, 1971](https://history.state.gov/milestones/1969-1976/south-asia)
- [Bangladesh Constitution: the declaration of independence, 26 March 1971](https://bdlaws.minlaw.gov.bd/act-367/section-24547.html)
- [United Nations: Former Trust and Non-Self-Governing Territories](https://www.un.org/dppa/decolonization/history/former-trust-and-nsgts)
- [United Nations: Decolonization history and independence dates](https://www.un.org/dppa/decolonization/sites/www.un.org.dppa.decolonization/files/decon_num_26-1.pdf)
- [UK Parliament: Legislative independence of the Dominions](https://www.parliament.uk/about/living-heritage/evolutionofparliament/legislativescrutiny/parliament-and-empire/parliament-and-the-american-colonies-before-1765/the-settler-colonies-legislative-independence/)
- [New Zealand History: Statute of Westminster enacted](https://nzhistory.govt.nz/statute-of-westminster-passed-confirming-nz-autonomy)

Runtime hook readback can confirm installation, but not long-campaign balance
or the campaign UI's response. Use a separate test save before keeping the mod
in a long-running campaign.
