import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import SearchForm from './SearchForm';

const meta: Meta<typeof SearchForm> = {
  title: 'Components/SearchForm',
  component: SearchForm,
  tags: ['autodocs'],
  argTypes: {
    onSearch: { action: 'searched' },
  },
};

export default meta;
type Story = StoryObj<typeof SearchForm>;

export const Default: Story = {};
