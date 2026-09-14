/**
 * One place that decides what a failure says out loud.
 *
 * The API's `detail` strings are written for whoever is holding the stack
 * trace — "the API is missing its OpenAI key", "We couldn't find that piece" —
 * and they were reaching musicians verbatim. Nothing from the server is shown
 * now except the session notice the client writes itself; each caller supplies
 * a sentence that makes sense where it appears, and the real error goes to the
 * console so it is still one keystroke away when something is actually wrong.
 */

import { ApiError } from "./api";

export function friendly(error: unknown, fallback: string): string {
  console.error("[nice-plates]", error);
  if (error instanceof ApiError) {
    // 401 is written by the client, not the server.
    return error.status === 401 ? error.message : fallback;
  }
  // A fetch that never got a response: offline, DNS, CORS, a sleeping instance.
  return "Can’t reach the server right now.";
}
