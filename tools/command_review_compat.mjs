// Existing suites exercise the preserved expanded command-review contracts.
// Balanced and situational-reasoning suites separately test their initial surfaces.
export async function openCommandReview(page,matchId){
 const scope=matchId?page.locator(`section[data-match-id="${matchId}"]`):page;
 if(matchId)await scope.waitFor();
 await scope.locator('[data-military-reasoning]:visible, [data-reasoning-invalid]:visible, [data-balanced-takeaway]:visible, [data-takeaway-invalid]:visible, [data-gameplay-review]:visible, [data-situation-status]:not([data-situation-status="loading"]):visible').first().waitFor();
 const panel=scope.locator('[data-full-command-review]');
 if(await panel.count()&&!await panel.evaluate(e=>e.open))await panel.locator(':scope > summary').click();
}
