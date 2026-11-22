// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import type { CoreComponent } from "../api/admin-api";
import { CoreComponentCard } from "./core-component-card";
import { NativeConsolesInfo } from "./native-consoles-info";

/** Presentational part of the core status page: pure data in, markup out (no queries). */
export function CoreStatusView({ components }: { components: readonly CoreComponent[] }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        {components.map((component) => (
          <CoreComponentCard key={component.key} component={component} />
        ))}
      </div>
      <NativeConsolesInfo />
    </div>
  );
}
