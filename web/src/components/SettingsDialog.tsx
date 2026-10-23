import { useEffect, useState } from "react";
import { getToken, setToken } from "../lib/storage";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Field } from "./Field";

export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [value, setValue] = useState("");
  useEffect(() => {
    if (open) setValue(getToken());
  }, [open]);
  return (
    <Dialog open={open} onClose={onClose} title="Settings">
      <form
        className="stack-sm"
        onSubmit={(e) => {
          e.preventDefault();
          setToken(value.trim());
          onClose();
        }}
      >
        <Field
          label="Access token"
          optional
          hint="Only needed when the server sets API_TOKEN. Stored in this browser only."
        >
          <input className="input" type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} />
        </Field>
        <div className="row row--end">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit">Save</Button>
        </div>
      </form>
    </Dialog>
  );
}
