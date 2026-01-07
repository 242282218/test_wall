export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state state--loading">
      <div className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}