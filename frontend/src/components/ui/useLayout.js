import { useOutletContext } from 'react-router-dom';

export default function useLayout() {
  const ctx = useOutletContext();
  return ctx || { openMenu: () => {}, openNotifications: () => {} };
}
