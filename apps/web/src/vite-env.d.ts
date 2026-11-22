// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Keycloak base URL incl. /auth. Default: http://localhost:9080/auth */
  readonly VITE_KEYCLOAK_URL?: string;
  /** Default: clew */
  readonly VITE_KEYCLOAK_REALM?: string;
  /** Default: clew-web */
  readonly VITE_KEYCLOAK_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
