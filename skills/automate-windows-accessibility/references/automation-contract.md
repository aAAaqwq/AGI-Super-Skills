# Windows automation contract

## Element contract

Require a snapshot element to expose, where available:

- snapshot-local token or index;
- process and top-level window identity;
- UIA control type and accessible name;
- automation ID and class name;
- physical screen rectangle;
- enabled and off-screen state;
- parent token and enough ancestry for contextual binding;
- supported patterns.

Accept an action target only when its exact semantic role and surrounding context agree. Reject a container whose aggregated accessible name merely contains the desired button label.

## Worker contract

- Run UIA provider calls outside the long-lived business thread.
- Set a hard timeout per request.
- Terminate and recreate the worker after a timeout.
- Invalidate all old tokens when the worker or snapshot changes.
- Attach the worker to a kill-on-parent-close mechanism where available.
- Distinguish timeout, provider failure, empty snapshot, window disappearance, and no match.

## Coordinate contract

1. Enable Per-Monitor DPI awareness before creating UI or reading geometry.
2. Define whether each rectangle is logical, client-physical, window-physical, or screen-physical.
3. Convert client offsets to physical pixels once.
4. Preserve the virtual desktop origin, including negative coordinates.
5. Normalize to the `SendInput` absolute range only at the final delivery step.
6. Recheck the target center lies inside the current visible window and monitor bounds.

## Action contract

For every action, define:

- target identity and exact semantic match;
- precondition and current state signature;
- visibility/scroll strategy;
- delivery method;
- expected state transition;
- retry count and reacquisition rule;
- failure artifact set;
- whether failure permits continuing the business process.

For web content, prefer foreground `SendInput`. For native controls, UIA `Invoke`, `SelectionItem`, `Toggle`, `ExpandCollapse`, `Scroll`, or `Value` may be appropriate. An exception-free pattern call still requires post-state verification.

## Identity and persistence contract

Do not join identity data from independent snapshots by list order. Capture stable identity and visible name in one coherent observation where possible. Before persistence, require an evidence chain such as:

```text
selected object identity
  -> visible panel identity
  -> action source/message identity
  -> newly opened unique preview
  -> downloaded file body and hash
  -> persisted owner identity
```

Any missing or conflicting edge must block the sensitive artifact from being attached to the record.

## Test matrix

- 100%, 125%, and 150% scaling.
- Primary and secondary monitors; negative virtual coordinates.
- Window restored, maximized, partially off-screen, and minimized.
- Virtualized list requiring repeated scroll and reacquisition.
- Duplicate names and duplicate button labels.
- Stale token after refresh, scroll, navigation, or worker restart.
- Click returns success but state does not change.
- Panel changes late or remains on the previous object.
- Modal dialog, sticky duplicate prompt, disabled/grey action, and delayed unlock.
- Worker timeout and provider hang.
- Ctrl-C, task stop, application crash, and parent exit cleanup.
- Login/challenge page circuit breaker.

Separate unit contracts, synthetic UI tests, installed-app tests, and real-account E2E evidence in reports.
