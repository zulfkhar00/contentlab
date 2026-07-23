# Settings screen audit (MVP screen 10)

Status: needs-info
Type: task

MVP spec lists a Settings screen. It was not touched in the S3 through S14 refactor. Scope needs sign-off from product owner before design.

Proposed scope:

  a. Channel connections (read-only for MVP) covering YouTube handle and Instagram handle
  b. Brand preset covering primary color, secondary color, logo URL
  c. Timezone used for experiment start time-stamps
  d. Danger zone to reset the localStorage seed

Open questions:

  a. Is the brand preset consumed anywhere yet? If not, defer this ticket.
  b. Do we need OAuth for channel connections in MVP, or is it stub-only?
  c. Where does the settings link live in the sidebar? Bottom, per usual pattern.

Done when this ticket is upgraded to ready-for-agent with a real scope.