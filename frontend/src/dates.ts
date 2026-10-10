export function readableDate(value: string): string {
  // Parse the calendar day at noon, avoiding UTC midnight shifts in the browser.
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}
