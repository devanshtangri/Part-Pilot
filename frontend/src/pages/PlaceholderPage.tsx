type PlaceholderPageProps = {
  title: string;
};

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section className="page-stack">
      <div className="page-header">
        <p className="eyebrow">Placeholder</p>
        <h1>{title}</h1>
        <p>This screen is part of the V1 navigation, but not part of Phase 1 implementation.</p>
      </div>
    </section>
  );
}
