import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import AvailabilityGraph from './AvailabilityGraph';

/**
 * The component fetches on mount, so each story stubs `fetch` rather than
 * taking props. The not-applicable state cannot be reached by rendering alone:
 * it depends on the API answering `applicable: false`, which it does under the
 * local backend.
 */
function stub(payload: unknown) {
  window.fetch = (async () =>
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as typeof window.fetch;
}

const meta: Meta<typeof AvailabilityGraph> = {
  title: 'Components/AvailabilityGraph',
  component: AvailabilityGraph,
  tags: ['autodocs'],
  parameters: {
    nextjs: { appDirectory: true, navigation: {} },
  },
};

export default meta;
type Story = StoryObj<typeof AvailabilityGraph>;

/** Local backend: the metric's source does not exist, so nothing is plotted. */
export const NotApplicable: Story = {
  // `load` was removed from story annotations in Storybook 10; `beforeEach`
  // runs before the story renders, which is when the fetch stub must be in place.
  beforeEach: () =>
    stub({
      applicable: false,
      backend: 'local',
      reason:
        'Availability is measured from the external VLM API, which is not in the request path under the local backend.',
      data: [],
    }),
};

/** LLM backend with a real series. */
export const WithSeries: Story = {
  beforeEach: () =>
    stub({
      applicable: true,
      data: Array.from({ length: 48 }, (_, i) => ({
        timestamp: new Date(Date.now() - (48 - i) * 15 * 60 * 1000).toISOString(),
        value: i % 9 === 0 ? 0 : 1,
      })),
    }),
};

/** Query succeeded but Prometheus has no points in the window. */
export const NoData: Story = {
  beforeEach: () => stub({ applicable: true, data: [] }),
};