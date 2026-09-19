-- RPC used by pluginMarketApi.incrementDownloads. No direct table write grant.
CREATE OR REPLACE FUNCTION public.increment_plugin_downloads(p_plugin_id text)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  UPDATE public.plugin_market
  SET downloads = COALESCE(downloads, 0) + 1
  WHERE plugin_id = p_plugin_id AND status = 'active';
$$;

REVOKE ALL ON FUNCTION public.increment_plugin_downloads(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.increment_plugin_downloads(text) TO authenticated;
