export function EmptyState({
  title = "Nothing here yet",
  description = "Try refreshing or adding something to your library."
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="state state--empty">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}