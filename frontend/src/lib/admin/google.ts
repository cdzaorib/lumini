// Minimal typing for Google Identity Services; the script is loaded only on /admin.
export const GOOGLE_SCRIPT = "https://accounts.google.com/gsi/client";

export type CredentialResponse = { credential?: string };

type IdConfiguration = {
  client_id: string;
  callback: (response: CredentialResponse) => void;
  auto_select?: boolean;
  cancel_on_tap_outside?: boolean;
  ux_mode?: "popup" | "redirect";
  use_fedcm_for_button?: boolean;
};

type ButtonOptions = {
  type?: "standard" | "icon";
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "large" | "medium" | "small";
  text?: "signin_with" | "signin" | "continue_with";
  shape?: "rectangular" | "pill";
  locale?: string;
};

export type GoogleAccountsId = {
  initialize(config: IdConfiguration): void;
  renderButton(parent: HTMLElement, options: ButtonOptions): void;
  disableAutoSelect(): void;
};

export function googleAccountsId(): GoogleAccountsId | null {
  const scope = window as unknown as { google?: { accounts?: { id?: GoogleAccountsId } } };
  return scope.google?.accounts?.id ?? null;
}
