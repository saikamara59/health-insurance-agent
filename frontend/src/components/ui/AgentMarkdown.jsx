import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

// Wide CMS comparison tables blow past a phone viewport. Wrap each one in
// a horizontally scrollable container so the user can swipe through it
// without the page itself going wider than the screen. iOS Safari ignores
// `overflow-x: auto` applied directly to a <table>, hence the wrapper.
const MD_COMPONENTS = {
  table: (props) => (
    <div className="agent-output-table-wrap">
      <table {...props} />
    </div>
  ),
};

/**
 * Renders an agent's freeform markdown response with Times New Roman prose
 * styling. Tables, lists, bold, and headings come through via remark-gfm so
 * we don't ship raw asterisks and pipes to the user. remark-breaks converts
 * single newlines to <br> so letter-style output (appeal letters, etc.)
 * keeps its visual structure without authors having to use double newlines.
 */
export default function AgentMarkdown({ children, className = '', style }) {
  return (
    <div className={`agent-output ${className}`.trim()} style={style}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={MD_COMPONENTS}
      >
        {children || ''}
      </ReactMarkdown>
    </div>
  );
}
